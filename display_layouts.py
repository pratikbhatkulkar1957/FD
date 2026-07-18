"""
How each bank publishes FD tables on its website.

The dashboard uses these layouts so tables look like the bank site
(separate amount tables vs side-by-side columns), not one common grid.
"""

from __future__ import annotations

# layout:
#   "separate"     → one HTML table per (fd_type, slab), like HDFC / IndusInd / Axis PDF
#   "side_by_side" → Tenure | <3 crore | 3–5 Cr in one table, like CUB

BANK_DISPLAY: dict[str, dict] = {
    "hdfc": {
        "layout": "separate",
        "note": "HDFC publishes separate tables for each deposit amount band.",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": "HDFC Bank — Domestic / NRE / NRO Fixed Deposits (Below ₹3 crore)",
                "tenure_header": "Tenure Bucket",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "callable",
                "slab": "3 Cr < 5 Cr",
                "title": "HDFC Bank — Fixed Deposits (₹3 crore to < ₹5 crore)",
                "tenure_header": "Period",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "3 Cr < 5 Cr",
                "title": "HDFC Bank — Non-Withdrawable Domestic / NRE / NRO Term Deposits",
                "tenure_header": "Period",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    },
    "cub": {
        "layout": "side_by_side",
        "note": "CUB shows <3 Cr and 3 Cr < 5 Cr as columns on the same tenure rows.",
        "tables": [
            {
                "fd_type": "callable",
                "title": "City Union Bank — Domestic / NRO Callable Term Deposit",
                "tenure_header": "Tenure",
                "under_header": "< 3 Crore",
                "three_header": "3 Cr < 5 Cr (Bulk)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "title": "City Union Bank — Non-Callable Deposit",
                "tenure_header": "Tenure",
                "under_header": "Above 1 Cr & Below 3 Cr",
                "three_header": "3 Cr < 5 Cr (Bulk)",
                "css_class": "non-callable",
            },
        ],
    },
    "axis": {
        "layout": "separate",
        "note": "Axis publishes rates in PDF tables by product (FD / FD Plus).",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": "Axis Bank — Domestic Fixed Deposits (Callable) — Less than ₹3 crore",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "callable",
                "slab": "3 Cr < 5 Cr",
                "title": "Axis Bank — Domestic Fixed Deposits (Callable) — ₹3 crore to < ₹5 crore",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "3 Cr < 5 Cr",
                "title": "Axis Bank — Fixed Deposits Plus (Non-Callable / Premature withdrawal not allowed)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    },
    "idfc": {
        "layout": "separate",
        "note": "IDFC publishes retail and bulk deposit rates in separate PDFs.",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": "IDFC FIRST Bank — Interest Rates on Retail Deposits (Callable, < ₹3 crore)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "callable",
                "slab": "3 Cr < 5 Cr",
                "title": "IDFC FIRST Bank — Bulk Deposits ₹3 Cr & above — Premature withdrawal permitted",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "3 Cr < 5 Cr",
                "title": "IDFC FIRST Bank — Bulk Deposits ₹3 Cr & above — Premature withdrawal not permitted",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    },
    "indusind": {
        "layout": "separate",
        "note": "IndusInd uses separate HTML tables for each amount band and withdrawal type.",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": "IndusInd Bank — Domestic Deposits < ₹3 Cr (Premature withdrawal allowed)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "callable",
                "slab": "3 Cr < 5 Cr",
                "title": "IndusInd Bank — ₹3 Cr to less than ₹5 Cr (Premature withdrawal allowed)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "<3 crore",
                "title": "IndusInd Bank — Above ₹1 Cr to less than ₹3 Cr (Premature withdrawal not allowed)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "3 Cr < 5 Cr",
                "title": "IndusInd Bank — ₹3 Cr to less than ₹5 Cr (Premature withdrawal not allowed)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    },
    "icici": {
        "layout": "side_by_side",
        "note": "ICICI FD rate feed lists amount slabs as columns on each tenure.",
        "tables": [
            {
                "fd_type": "callable",
                "title": "ICICI Bank — Fixed Deposit Interest Rates (Callable / Premature withdrawal allowed)",
                "tenure_header": "Tenure",
                "under_header": "Below ₹2 Cr / < ₹3 Cr",
                "three_header": "₹2 Cr to < ₹5 Cr",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "title": "ICICI Bank — Fixed Deposit Interest Rates (Non-Callable)",
                "tenure_header": "Tenure",
                "under_header": "Below ₹2 Cr / < ₹3 Cr",
                "three_header": "₹2 Cr to < ₹5 Cr",
                "css_class": "non-callable",
            },
        ],
    },
    "sbi": {
        "layout": "separate",
        "note": "SBI retail page publishes tenure vs public rates in one main column.",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": "SBI — Retail Domestic Term Deposits (Callable) — General Public",
                "tenure_header": "Tenors",
                "rate_header": "Rates for Public (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "<3 crore",
                "title": "SBI — Domestic Term Deposits (Non-Callable) — General Public",
                "tenure_header": "Tenors",
                "rate_header": "Rates for Public (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    },
    "yes_bank": {
        "layout": "separate",
        "note": "Yes Bank: callable <3 Cr on website table; bulk 3–5 Cr in PDF.",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": "YES BANK — Fixed Deposit Interest Rates (Callable, below ₹3 crore)",
                "tenure_header": "Period",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "callable",
                "slab": "3 Cr < 5 Cr",
                "title": "YES BANK — Bulk Fixed Deposit (Callable, ₹3 Cr to < ₹5 Cr) — from PDF",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "3 Cr < 5 Cr",
                "title": "YES BANK — Bulk Fixed Deposit (Non-Callable, ₹3 Cr to < ₹5 Cr) — from PDF",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    },
}


def get_bank_display(slug: str) -> dict:
    """Return display config for a bank, or a safe separate-table default."""
    if slug in BANK_DISPLAY:
        return BANK_DISPLAY[slug]
    return {
        "layout": "separate",
        "note": "Bank-native tenures as scraped from the official source.",
        "tables": [
            {
                "fd_type": "callable",
                "slab": "<3 crore",
                "title": f"{slug.upper()} — Callable (< ₹3 crore)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "callable",
                "slab": "3 Cr < 5 Cr",
                "title": f"{slug.upper()} — Callable (₹3 Cr < ₹5 Cr)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "<3 crore",
                "title": f"{slug.upper()} — Non-Callable (< ₹3 crore)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
            {
                "fd_type": "non_callable",
                "slab": "3 Cr < 5 Cr",
                "title": f"{slug.upper()} — Non-Callable (₹3 Cr < ₹5 Cr)",
                "tenure_header": "Tenure",
                "rate_header": "Interest Rate (% p.a.)",
                "css_class": "non-callable",
            },
        ],
    }
