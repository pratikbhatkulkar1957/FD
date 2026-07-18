"""
Local JSON archive for each scrape run.

Every Refresh Rates creates:
  data/scrapes/<YYYY-MM-DD_HH-MM-SS>/
    summary.json
    hdfc/rates.json
    axis/rates.json
    ...

Useful for debugging without querying MySQL.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bank_data import BANKS
from config import settings


def create_scrape_session() -> Path | None:
    """Create a timestamped folder for one scrape run (skipped if disk is unavailable)."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        session_dir = Path(settings.SCRAPES_DIR) / ts
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
    except OSError:
        return None


def save_bank_scrape(
    session_dir: Path | None,
    bank_slug: str,
    points: list | None,
    *,
    error: str | None = None,
) -> None:
    """Write one bank's scraped points (or error) to rates.json."""
    if session_dir is None:
        return
    bank_dir = session_dir / bank_slug
    bank_dir.mkdir(parents=True, exist_ok=True)

    rates = []
    if points:
        for p in points:
            rates.append({
                "fd_type": p.fd_type,
                "tenure_label": p.tenure_label,
                "tenure_min_days": p.tenure_min_days,
                "tenure_max_days": p.tenure_max_days,
                "deposit_slab": p.deposit_slab,
                "sort_order": p.sort_order,
                "rate_percent": str(Decimal(p.rate_percent).quantize(Decimal("0.01"))),
                "source_url": p.source_url,
            })

    payload = {
        "bank_slug": bank_slug,
        "bank_name": BANKS.get(bank_slug, {}).get("name", bank_slug.upper()),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "rates": rates,
    }
    (bank_dir / "rates.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_scrape_summary(session_dir: Path | None, results: list) -> None:
    """Write summary.json with success/fail counts for the whole run."""
    if session_dir is None:
        return
    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "session_folder": str(session_dir.name),
        "banks": [
            {
                "bank_slug": r.bank_slug,
                "bank_name": BANKS.get(r.bank_slug, {}).get("name", r.bank_slug),
                "points_seen": r.points_seen,
                "changed_points": r.changed_points,
                "error": r.error,
            }
            for r in results
        ],
        "success_count": sum(1 for r in results if not r.error),
        "failed_count": sum(1 for r in results if r.error),
    }
    (session_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
