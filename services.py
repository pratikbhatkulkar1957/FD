"""
Business logic for scraping and building dashboard/compare views.

Dashboard shows each bank as published on the bank website (native tenures).
Filters + best-rate helpers live here; main.py only calls these functions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta, timezone
from decimal import Decimal

import db_storage
from bank_data import BANKS, TENURE_ROWS, all_bank_slugs, get_source_url
from display_layouts import get_bank_display
from rate_scrapers import SCRAPERS as LIVE_SCRAPERS
from scrape_archive import create_scrape_session, save_bank_scrape, save_scrape_summary
from scrapers import get_scraper

# Shown in UI when a bank has no published rate for that tenure/slab.
MISSING_VALUE = "—"


def format_last_updated(dt) -> str | None:
    """Format a UTC datetime as IST for the dashboard header."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
    return ist.strftime("%d %b %Y, %I:%M %p IST")


@dataclass(frozen=True)
class ScrapeResult:
    """Outcome of scraping one bank (returned to APIs / scrape summary)."""

    bank_slug: str
    points_seen: int
    changed_points: int
    error: str | None = None


def scrape_banks(bank_slugs: list[str] | None = None) -> list[ScrapeResult]:
    """
    Refresh rates for the given banks (or all live scrapers).

    For each bank:
      1. Clear old fd_rates rows
      2. Fetch live rates from the official site
      3. Upsert into MySQL + write history on changes
      4. Archive JSON under data/scrapes/<timestamp>/
    On failure, clears that bank's rates so stale data is not shown.
    """
    if bank_slugs is None:
        bank_slugs = list(LIVE_SCRAPERS.keys())

    db_storage.ensure_banks_exist(all_bank_slugs())

    for slug in all_bank_slugs():
        if slug not in LIVE_SCRAPERS:
            db_storage.clear_bank_rates(slug)

    results: list[ScrapeResult] = []
    session_dir = create_scrape_session()

    for slug in bank_slugs:
        scraper = get_scraper(slug)
        if scraper is None:
            db_storage.clear_bank_rates(slug)
            result = ScrapeResult(slug, 0, 0, error="No scraper configured")
            save_bank_scrape(session_dir, slug, None, error=result.error)
            results.append(result)
            continue
        try:
            db_storage.clear_bank_rates(slug)
            points = scraper.fetch_rates()
            changed_points = db_storage.upsert_rates_and_record_history(slug, points)
            save_bank_scrape(session_dir, slug, points)
            results.append(
                ScrapeResult(
                    bank_slug=slug,
                    points_seen=len(points),
                    changed_points=changed_points,
                )
            )
        except Exception as exc:
            db_storage.clear_bank_rates(slug)
            result = ScrapeResult(slug, 0, 0, error=str(exc))
            save_bank_scrape(session_dir, slug, None, error=result.error)
            results.append(result)

    save_scrape_summary(session_dir, results)
    return results


def filter_rates(
    rates: list,
    *,
    bank_slug: str | None = None,
    fd_type: str | None = None,
    deposit_slab: str | None = None,
    tenure_days: int | None = None,
) -> list:
    """Apply dashboard filters. Pass None / 'all' to skip a filter."""
    out = list(rates)
    if bank_slug and bank_slug != "all":
        out = [r for r in out if r.bank_slug == bank_slug]
    if fd_type and fd_type != "all":
        out = [r for r in out if r.fd_type == fd_type]
    if deposit_slab and deposit_slab != "all":
        out = [r for r in out if r.deposit_slab == deposit_slab]
    if tenure_days is not None:
        out = [
            r for r in out
            if r.tenure_min_days <= tenure_days <= r.tenure_max_days
        ]
    return out


def banks_with_rates(rates: list) -> list[str]:
    """Bank slugs that currently have at least one rate row."""
    slugs = {r.bank_slug for r in rates}
    return [s for s in all_bank_slugs() if s in slugs]


def find_best_overall(rates: list) -> dict | None:
    """
    Highest rate among the (already filtered) list.
    Used for the 'Best rate for your filters' card.
    """
    if not rates:
        return None
    best = max(rates, key=lambda r: Decimal(r.rate_percent))
    return {
        "bank_slug": best.bank_slug,
        "bank_name": _bank_name(best.bank_slug),
        "fd_type": best.fd_type,
        "fd_type_label": "Callable" if best.fd_type == "callable" else "Non-Callable",
        "tenure_label": best.tenure_label,
        "deposit_slab": best.deposit_slab,
        "rate_percent": _fmt_rate(best),
        "source_url": best.source_url or get_source_url(best.bank_slug, best.fd_type),
    }


def _best_rate_keys(rates: list) -> set[tuple]:
    """
    Keys (bank, fd_type, tenure, slab) that equal the global best for the same
    deposit slab among overlapping day ranges — used to highlight table cells.
    """
    if not rates:
        return set()

    by_slab: dict[str, list] = defaultdict(list)
    for r in rates:
        by_slab[r.deposit_slab].append(r)

    winners: set[tuple] = set()
    for slab, group in by_slab.items():
        top = max(Decimal(r.rate_percent) for r in group)
        for r in group:
            if Decimal(r.rate_percent) == top:
                winners.add((r.bank_slug, r.fd_type, r.tenure_label, r.deposit_slab))
    return winners


def build_bank_tables(
    rates: list,
    *,
    bank_slug: str | None = None,
    fd_type: str | None = None,
    deposit_slab: str | None = None,
    tenure_days: int | None = None,
) -> list[dict]:
    """
    Build tables that mirror how each bank presents rates on its website.

    - "separate" layout  → one table per amount slab (HDFC, Axis PDF, IndusInd, …)
    - "side_by_side"     → Tenure | <3 Cr | 3–5 Cr on one table (CUB, ICICI)
    Tenures stay as published by the bank (never remapped).
    """
    filtered = filter_rates(
        rates,
        bank_slug=bank_slug,
        fd_type=fd_type,
        deposit_slab=deposit_slab,
        tenure_days=tenure_days,
    )
    best_keys = _best_rate_keys(filtered)
    available = banks_with_rates(filtered)

    tables: list[dict] = []
    rates_by_bank: dict[str, list] = defaultdict(list)
    for r in filtered:
        rates_by_bank[r.bank_slug].append(r)

    for slug in available:
        bank_name = BANKS.get(slug, {}).get("name", slug.upper())
        bank_rates = rates_by_bank.get(slug, [])
        display = get_bank_display(slug)
        layout = display.get("layout", "separate")

        for section in display.get("tables", []):
            sec_fd = section["fd_type"]
            if fd_type and fd_type != "all" and sec_fd != fd_type:
                continue

            type_rates = [r for r in bank_rates if r.fd_type == sec_fd]
            if not type_rates:
                continue

            source_url = get_source_url(slug, sec_fd)
            if type_rates[0].source_url:
                source_url = type_rates[0].source_url

            if layout == "side_by_side":
                table = _build_side_by_side_table(
                    slug=slug,
                    bank_name=bank_name,
                    section=section,
                    type_rates=type_rates,
                    best_keys=best_keys,
                    deposit_slab_filter=deposit_slab,
                    source_url=source_url,
                    note=display.get("note"),
                )
            else:
                sec_slab = section.get("slab")
                if deposit_slab and deposit_slab != "all" and sec_slab != deposit_slab:
                    continue
                table = _build_separate_table(
                    slug=slug,
                    bank_name=bank_name,
                    section=section,
                    type_rates=type_rates,
                    best_keys=best_keys,
                    source_url=source_url,
                    note=display.get("note"),
                )

            if table is not None:
                tables.append(table)

    return tables


def build_bank_groups(
    rates: list,
    *,
    bank_slug: str | None = None,
    fd_type: str | None = None,
    deposit_slab: str | None = None,
    tenure_days: int | None = None,
) -> list[dict]:
    """Group website-style tables under each bank for the dashboard."""
    tables = build_bank_tables(
        rates,
        bank_slug=bank_slug,
        fd_type=fd_type,
        deposit_slab=deposit_slab,
        tenure_days=tenure_days,
    )
    groups: list[dict] = []
    by_slug: dict[str, dict] = {}
    for table in tables:
        slug = table["bank_slug"]
        if slug not in by_slug:
            group = {
                "bank_slug": slug,
                "bank_name": table["bank_name"],
                "note": table.get("note"),
                "tables": [],
            }
            by_slug[slug] = group
            groups.append(group)
        by_slug[slug]["tables"].append(table)
    return groups


def _ordered_tenure_map(type_rates: list) -> tuple[list[str], dict[str, dict]]:
    """Preserve bank website row order: tenure_label -> {slab: rate_row}."""
    by_tenure: dict[str, dict] = {}
    order: list[str] = []
    for r in sorted(type_rates, key=lambda x: (x.sort_order, x.tenure_label)):
        if r.tenure_label not in by_tenure:
            by_tenure[r.tenure_label] = {}
            order.append(r.tenure_label)
        by_tenure[r.tenure_label][r.deposit_slab] = r
    return order, by_tenure


def _build_separate_table(
    *,
    slug: str,
    bank_name: str,
    section: dict,
    type_rates: list,
    best_keys: set,
    source_url: str,
    note: str | None,
) -> dict | None:
    """One rate column — matches banks that publish one amount table at a time."""
    slab = section["slab"]
    fd = section["fd_type"]
    order, by_tenure = _ordered_tenure_map(type_rates)
    rows = []
    for label in order:
        rate_row = by_tenure[label].get(slab)
        if rate_row is None:
            continue
        rows.append({
            "tenure_label": label,
            "rate": _fmt_rate(rate_row),
            "is_best": (slug, fd, label, slab) in best_keys,
        })
    if not rows:
        return None
    return {
        "bank_slug": slug,
        "bank_name": bank_name,
        "fd_type": fd,
        "layout": "separate",
        "dual_slab": False,
        "title": section["title"],
        "tenure_header": section.get("tenure_header", "Tenure"),
        "rate_header": section.get("rate_header", "Interest Rate (% p.a.)"),
        "single_slab_label": section.get("rate_header", slab),
        "css_class": section.get("css_class", "callable"),
        "source_url": source_url,
        "note": note,
        "rows": rows,
    }


def _build_side_by_side_table(
    *,
    slug: str,
    bank_name: str,
    section: dict,
    type_rates: list,
    best_keys: set,
    deposit_slab_filter: str | None,
    source_url: str,
    note: str | None,
) -> dict | None:
    """Two amount columns — matches CUB / ICICI style pages."""
    fd = section["fd_type"]
    show_under = deposit_slab_filter in (None, "all", "<3 crore")
    show_three = deposit_slab_filter in (None, "all", "3 Cr < 5 Cr")
    order, by_tenure = _ordered_tenure_map(type_rates)
    rows = []

    if show_under and show_three:
        for label in order:
            under_row = by_tenure[label].get("<3 crore")
            three_row = by_tenure[label].get("3 Cr < 5 Cr")
            if under_row is None and three_row is None:
                continue
            rows.append({
                "tenure_label": label,
                "under_3cr": _fmt_rate(under_row),
                "three_to_5cr": _fmt_rate(three_row),
                "under_3cr_best": under_row is not None and (slug, fd, label, "<3 crore") in best_keys,
                "three_to_5cr_best": three_row is not None and (slug, fd, label, "3 Cr < 5 Cr") in best_keys,
            })
        dual = True
        single_label = None
    elif show_under:
        for label in order:
            under_row = by_tenure[label].get("<3 crore")
            if under_row is None:
                continue
            rows.append({
                "tenure_label": label,
                "rate": _fmt_rate(under_row),
                "is_best": (slug, fd, label, "<3 crore") in best_keys,
            })
        dual = False
        single_label = section.get("under_header", "<3 crore")
    else:
        for label in order:
            three_row = by_tenure[label].get("3 Cr < 5 Cr")
            if three_row is None:
                continue
            rows.append({
                "tenure_label": label,
                "rate": _fmt_rate(three_row),
                "is_best": (slug, fd, label, "3 Cr < 5 Cr") in best_keys,
            })
        dual = False
        single_label = section.get("three_header", "3 Cr < 5 Cr")

    if not rows:
        return None
    return {
        "bank_slug": slug,
        "bank_name": bank_name,
        "fd_type": fd,
        "layout": "side_by_side",
        "dual_slab": dual,
        "title": section["title"],
        "tenure_header": section.get("tenure_header", "Tenure"),
        "under_header": section.get("under_header", "<3 crore"),
        "three_header": section.get("three_header", "3 Cr < 5 Cr"),
        "rate_header": single_label,
        "single_slab_label": single_label,
        "css_class": section.get("css_class", "callable"),
        "source_url": source_url,
        "note": note,
        "rows": rows,
    }


def _fmt_rate(rate_row) -> str:
    """Format a DB rate row as '6.75%' or return MISSING_VALUE if absent."""
    if rate_row is None:
        return MISSING_VALUE
    return f"{Decimal(rate_row.rate_percent).quantize(Decimal('0.01'))}%"


def _bank_name(slug: str) -> str:
    return BANKS.get(slug, {}).get("name", slug.upper())


def _best_covering_day(rates: list, day: int, slab: str):
    """Best bank rate whose tenure covers `day` for the given slab."""
    candidates = [
        r for r in rates
        if r.deposit_slab == slab and r.tenure_min_days <= day <= r.tenure_max_days
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: Decimal(r.rate_percent))


def build_best_rate_comparison(rates: list, fd_type: str = "callable") -> list[dict]:
    """
    Compare best rates across banks for standard day anchors.
    Uses each bank's native tenure bands (any band covering that day).
    """
    filtered = [r for r in rates if r.fd_type == fd_type]
    rows: list[dict] = []

    for tenure in TENURE_ROWS:
        day = tenure["min_days"]
        best_under = _best_covering_day(filtered, day, "<3 crore")
        best_three = _best_covering_day(filtered, day, "3 Cr < 5 Cr")
        if best_under is None and best_three is None:
            continue
        rows.append({
            "tenure_label": tenure["label"],
            "under_3cr_rate": _fmt_rate(best_under),
            "under_3cr_bank": _bank_name(best_under.bank_slug) if best_under else MISSING_VALUE,
            "under_3cr_tenure": best_under.tenure_label if best_under else MISSING_VALUE,
            "three_to_5cr_rate": _fmt_rate(best_three),
            "three_to_5cr_bank": _bank_name(best_three.bank_slug) if best_three else MISSING_VALUE,
            "three_to_5cr_tenure": best_three.tenure_label if best_three else MISSING_VALUE,
        })

    return rows


def build_ranked_rates(
    rates: list,
    tenure_label: str,
    fd_type: str,
    slab: str,
) -> list[dict]:
    """
    Rank banks for a standard tenure anchor day (from TENURE_ROWS label).
    Uses band coverage, not exact label match.
    """
    day = next((t["min_days"] for t in TENURE_ROWS if t["label"] == tenure_label), None)
    if day is None:
        return []
    filtered = [
        r for r in rates
        if r.fd_type == fd_type
        and r.deposit_slab == slab
        and r.tenure_min_days <= day <= r.tenure_max_days
    ]
    filtered.sort(key=lambda r: Decimal(r.rate_percent), reverse=True)
    return [
        {
            "rank": idx,
            "bank_name": _bank_name(r.bank_slug),
            "bank_slug": r.bank_slug,
            "tenure_label": r.tenure_label,
            "rate_percent": _fmt_rate(r),
        }
        for idx, r in enumerate(filtered, start=1)
    ]
