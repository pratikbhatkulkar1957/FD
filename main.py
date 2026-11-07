"""
FastAPI entry point for the FD Rates Tracker.

This file only defines HTTP routes and app lifecycle.
Business logic lives in services.py; MySQL access lives in db_storage.py.
"""

import csv
import io
import logging
from decimal import Decimal

import pymysql
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

import db_storage
from bank_data import BANKS, all_bank_slugs
from config import settings
from schemas import BankOut, BestRateOut, RateOut
from services import (
    build_bank_groups,
    build_best_rate_comparison,
    build_ranked_rates,
    banks_with_rates,
    find_best_overall,
    format_last_updated,
    scrape_banks,
)


app = FastAPI(title="FD Rates (FastAPI + MySQL)")
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


@app.on_event("startup")
def _startup() -> None:
    """Optional DB init / scrape on boot (both off by default for Hostinger)."""
    try:
        if settings.INIT_DB_ON_STARTUP:
            db_storage.init_db()
        if settings.SCRAPE_ON_STARTUP:
            scrape_banks()
    except pymysql.err.OperationalError as exc:
        # App still starts; pages will retry MySQL on the next request.
        logger.warning("MySQL unavailable at startup (%s). App will retry on next request.", exc)
    except Exception:
        logger.exception("Startup task failed")


@app.on_event("shutdown")
def _shutdown() -> None:
    """Close the shared MySQL connection cleanly when the server stops."""
    db_storage.close_db()


def _bank_lookup() -> dict[str, BankOut]:
    """Return bank slug -> BankOut from bank_data (canonical list for APIs)."""
    return {slug: BankOut(slug=slug, name=meta["name"]) for slug, meta in BANKS.items()}


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    bank_slug: str | None = Query(default=None),
    fd_type: str = Query(default="all", pattern="^(all|callable|non_callable)$"),
    deposit_slab: str = Query(default="all"),
    tenure_days: str | None = Query(default=None),
    scraped: int | None = Query(default=None),
    failed: str | None = Query(default=None),
):
    """
    Dashboard: each bank table uses that bank's own tenure rows (website style).

    Filters: bank, FD type, deposit slab, optional tenure days (e.g. 444).
    Best-rate card uses the same filters.
    """
    # Empty form fields come through as "" — treat those as "no filter".
    if bank_slug == "":
        bank_slug = None
    parsed_days: int | None = None
    if tenure_days is not None and str(tenure_days).strip() != "":
        try:
            parsed_days = int(str(tenure_days).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="tenure_days must be a number") from exc
        if parsed_days < 1 or parsed_days > 5000:
            raise HTTPException(status_code=400, detail="tenure_days must be between 1 and 5000")

    if deposit_slab not in ("all", "<3 crore", "3 Cr < 5 Cr"):
        raise HTTPException(status_code=400, detail="Invalid deposit_slab")
    if bank_slug and bank_slug not in BANKS:
        raise HTTPException(status_code=404, detail="Bank not found")

    dashboard_data = db_storage.get_dashboard_data()
    rates = dashboard_data.rates
    live_banks = banks_with_rates(rates)

    bank_groups = build_bank_groups(
        rates,
        bank_slug=bank_slug,
        fd_type=fd_type,
        deposit_slab=deposit_slab,
        tenure_days=parsed_days,
    )
    filtered_common = [
        r for r in rates
        if (not bank_slug or r.bank_slug == bank_slug)
        and (deposit_slab == "all" or r.deposit_slab == deposit_slab)
        and (parsed_days is None or r.tenure_min_days <= parsed_days <= r.tenure_max_days)
    ]
    best_callable = (
        find_best_overall([r for r in filtered_common if r.fd_type == "callable"])
        if fd_type in ("all", "callable")
        else None
    )
    best_non_callable = (
        find_best_overall([r for r in filtered_common if r.fd_type == "non_callable"])
        if fd_type in ("all", "non_callable")
        else None
    )

    banks = [BankOut(slug=s, name=BANKS[s]["name"]) for s in all_bank_slugs()]
    pending_banks = [b for b in banks if b.slug not in live_banks]
    last_updated = format_last_updated(dashboard_data.last_updated)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "banks": banks,
            "live_banks": live_banks,
            "pending_banks": pending_banks,
            "bank_groups": bank_groups,
            "best_callable": best_callable,
            "best_non_callable": best_non_callable,
            "selected_bank": bank_slug,
            "selected_fd_type": fd_type,
            "selected_slab": deposit_slab,
            "tenure_days": parsed_days,
            "scraped": scraped == 1,
            "scrape_failed": failed,
            "no_data": len(rates) == 0,
            "bank_has_no_data": bank_slug is not None and bank_slug not in live_banks,
            "last_updated": last_updated,
            "stats": {
                "banks": len(BANKS),
                "rates": len(rates),
                "history": dashboard_data.history_count,
            },
        },
    )


@app.get("/compare", response_class=HTMLResponse)
def compare_page(
    request: Request,
    fd_type: str = Query(default="callable", pattern="^(callable|non_callable)$"),
):
    """Best-rate comparison page across all banks for one FD type."""
    rates = db_storage.get_rates()
    best_rows = build_best_rate_comparison(rates, fd_type=fd_type)

    # Full ranking lists used under the best-rate summary table.
    tenures = [row["tenure_label"] for row in best_rows]
    rankings: dict[str, dict[str, list]] = {}
    for tenure in tenures:
        rankings[tenure] = {
            "<3 crore": build_ranked_rates(rates, tenure, fd_type, "<3 crore"),
            "3 Cr < 5 Cr": build_ranked_rates(rates, tenure, fd_type, "3 Cr < 5 Cr"),
        }

    fd_type_label = "Callable FD" if fd_type == "callable" else "Non-Callable FD"
    last_updated = format_last_updated(db_storage.get_last_updated())

    return templates.TemplateResponse(
        "compare.html",
        {
            "request": request,
            "fd_type": fd_type,
            "fd_type_label": fd_type_label,
            "best_rows": best_rows,
            "tenures": tenures,
            "rankings": rankings,
            "last_updated": last_updated,
        },
    )


# ---------------------------------------------------------------------------
# JSON APIs
# ---------------------------------------------------------------------------

@app.get("/rates/compare/best", response_model=list[BestRateOut])
def best_rates_api(
    fd_type: str = Query(default="callable", pattern="^(callable|non_callable)$"),
    deposit_slab: str | None = Query(default=None),
):
    """API: highest rate per tenure/slab for the given FD type."""
    banks = _bank_lookup()
    rates = db_storage.get_rates()
    filtered = [r for r in rates if r.fd_type == fd_type]
    if deposit_slab:
        filtered = [r for r in filtered if r.deposit_slab == deposit_slab]

    best_by_key: dict[tuple[str, str], object] = {}
    for r in filtered:
        key = (r.tenure_label, r.deposit_slab)
        existing = best_by_key.get(key)
        if existing is None or Decimal(r.rate_percent) > Decimal(existing.rate_percent):
            best_by_key[key] = r

    results: list[BestRateOut] = []
    for (tenure_label, slab), r in sorted(best_by_key.items()):
        bank = banks.get(r.bank_slug, BankOut(slug=r.bank_slug, name=r.bank_slug.upper()))
        results.append(
            BestRateOut(
                tenure_label=tenure_label,
                fd_type=fd_type,
                deposit_slab=slab,
                rate_percent=Decimal(r.rate_percent).quantize(Decimal("0.01")),
                bank=bank,
            )
        )
    return results


@app.get("/banks", response_model=list[BankOut])
def list_banks():
    """API: all configured banks."""
    return list(_bank_lookup().values())


@app.get("/rates", response_model=list[RateOut])
def list_rates(bank_slug: str | None = Query(default=None)):
    """API: current FD rates, optionally filtered by bank."""
    banks = _bank_lookup()
    rates = db_storage.get_rates()
    if bank_slug:
        rates = [r for r in rates if r.bank_slug == bank_slug]

    return [
        RateOut(
            bank=banks.get(r.bank_slug, BankOut(slug=r.bank_slug, name=r.bank_slug.upper())),
            fd_type=r.fd_type,
            tenure_label=r.tenure_label,
            tenure_min_days=r.tenure_min_days,
            tenure_max_days=r.tenure_max_days,
            deposit_slab=r.deposit_slab,
            rate_percent=Decimal(r.rate_percent).quantize(Decimal("0.01")),
            source_url=r.source_url,
            updated_at=r.updated_at,
        )
        for r in rates
    ]


# ---------------------------------------------------------------------------
# Scrape + export
# ---------------------------------------------------------------------------

@app.post("/scrape/run-page")
def run_scrape_page():
    """
    Called by the nav 'Refresh Rates' button.
    Scrapes all banks, then redirects back to the dashboard with a status flag.
    """
    results = scrape_banks()
    failed = [r for r in results if r.error]
    if failed:
        names = ",".join(r.bank_slug for r in failed)
        return RedirectResponse(url=f"/?scraped=0&failed={names}", status_code=303)
    return RedirectResponse(url="/?scraped=1", status_code=303)


@app.post("/scrape/run")
def run_scrape(
    banks: str = Query(",".join(all_bank_slugs()), description="Comma-separated bank slugs"),
):
    """API: scrape selected banks and return JSON results (no redirect)."""
    bank_slugs = [b.strip().lower() for b in banks.split(",") if b.strip()]
    if not bank_slugs:
        raise HTTPException(status_code=400, detail="No banks provided")

    results = scrape_banks(bank_slugs)
    return {"results": [r.__dict__ for r in results]}


@app.get("/export/csv")
def export_csv():
    """Download current rates as CSV."""
    banks_map = _bank_lookup()
    rates = db_storage.get_rates()
    rates.sort(key=lambda r: (r.bank_slug, r.fd_type, r.sort_order, r.deposit_slab))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "bank", "fd_type", "tenure_label", "tenure_min_days", "tenure_max_days",
        "deposit_slab", "rate_percent", "source_url", "updated_at",
    ])
    for r in rates:
        bank = banks_map.get(r.bank_slug, BankOut(slug=r.bank_slug, name=r.bank_slug.upper()))
        writer.writerow([
            bank.name,
            r.fd_type,
            r.tenure_label,
            r.tenure_min_days,
            r.tenure_max_days,
            r.deposit_slab,
            float(r.rate_percent),
            r.source_url or "",
            r.updated_at.isoformat() if r.updated_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fd_rates.csv"},
    )


@app.get("/export/excel")
def export_excel():
    """Download current rates as Excel (.xlsx)."""
    path = db_storage.export_to_excel()
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="fd_rates.xlsx",
    )
