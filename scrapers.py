"""
Adapter between live scrapers (rate_scrapers.py) and MySQL (RatePoint).

Each bank scraper returns rates with the bank's own tenure labels:
  { "callable": { "7 days to 14 days": {"<3 crore": Decimal("4.40"), ...}, ... }, ... }

This module flattens that into a list[RatePoint] for db_storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from bank_data import get_source_url
from rate_scrapers import SCRAPERS as LIVE_SCRAPERS, parse_tenor_range, scrape_bank
from schemas import RatePoint


class BankScraper(Protocol):
    """Interface every bank scraper wrapper must implement."""

    slug: str

    def fetch_rates(self) -> list[RatePoint]:
        raise NotImplementedError


@dataclass(frozen=True)
class LiveBankScraper:
    """Calls the live scrape_* function for one bank and builds RatePoints."""

    slug: str

    def fetch_rates(self) -> list[RatePoint]:
        data = scrape_bank(self.slug)
        if not data:
            raise RuntimeError(f"No live scraper available for {self.slug}")

        out: list[RatePoint] = []
        sort_order = 0
        for fd_type, tenure_rates in data.items():
            source_url = get_source_url(self.slug, fd_type)
            # Preserve bank website row order.
            for label, slab_rates in tenure_rates.items():
                if not slab_rates:
                    continue
                sort_order += 1
                min_days, max_days = parse_tenor_range(label)
                for slab, rate in slab_rates.items():
                    out.append(
                        RatePoint(
                            fd_type=fd_type,
                            tenure_label=label,
                            tenure_min_days=max(1, min_days),
                            tenure_max_days=max(1, max_days),
                            deposit_slab=slab,
                            sort_order=sort_order,
                            rate_percent=Decimal(rate),
                            source_url=source_url,
                        )
                    )
        if not out:
            raise RuntimeError(f"Could not fetch rates for {self.slug}")
        return out


# One LiveBankScraper instance per bank that has a working scrape_* function.
SCRAPERS: dict[str, BankScraper] = {
    slug: LiveBankScraper(slug=slug) for slug in LIVE_SCRAPERS
}


def get_scraper(slug: str) -> BankScraper | None:
    """Return the scraper wrapper for a bank slug, or None if not configured."""
    return SCRAPERS.get(slug)
