"""
Pydantic models for API requests/responses and scraped rate points.

These define the shape of data returned by FastAPI JSON endpoints
and the objects written into MySQL after a scrape.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BankOut(BaseModel):
    """Bank identity for API responses."""

    slug: str
    name: str


class RatePoint(BaseModel):
    """
    One scraped rate cell, ready to save into fd_rates.

    Built by scrapers.py from each bank's live scrape result.
    """

    fd_type: str = Field(..., description="callable or non_callable")
    tenure_label: str
    tenure_min_days: int = Field(..., ge=1)
    tenure_max_days: int = Field(..., ge=1)
    deposit_slab: str
    sort_order: int = 0
    rate_percent: Decimal
    source_url: str | None = None


class RateOut(BaseModel):
    """Current rate row returned by GET /rates."""

    bank: BankOut
    fd_type: str
    tenure_label: str
    tenure_min_days: int
    tenure_max_days: int
    deposit_slab: str
    rate_percent: Decimal
    source_url: str | None = None
    updated_at: datetime | None = None


class HistoryOut(BaseModel):
    """One historical rate-change event (API shape)."""

    bank: BankOut
    fd_type: str
    tenure_label: str
    deposit_slab: str
    rate_percent: Decimal
    source_url: str | None = None
    changed_at: datetime | None = None


class BestRateOut(BaseModel):
    """Best rate across banks for one tenure + slab."""

    tenure_label: str
    fd_type: str
    deposit_slab: str
    rate_percent: Decimal
    bank: BankOut
