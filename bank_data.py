"""
Bank metadata and the standard CUB-style tenure grid.

Every bank scraper's output is mapped onto TENURE_ROWS + DEPOSIT_SLABS
so the dashboard tables look the same for all banks.
"""

# Standard tenure rows shown in dashboard / compare tables (CUB format).
TENURE_ROWS = [
    {"label": "365 days to 443 days", "min_days": 365, "max_days": 443, "sort": 1},
    {"label": "444 days", "min_days": 444, "max_days": 444, "sort": 2},
    {"label": "445 days to 554 days", "min_days": 445, "max_days": 554, "sort": 3},
    {"label": "555 days", "min_days": 555, "max_days": 555, "sort": 4},
    {"label": "556 days to 3 Years", "min_days": 556, "max_days": 1095, "sort": 5},
]

# Deposit amount slabs shown as table columns.
DEPOSIT_SLABS = ["<3 crore", "3 Cr < 5 Cr"]

# bank slug -> display name + official source URLs per FD type.
BANKS: dict[str, dict] = {
    "yes_bank": {
        "name": "Yes Bank",
        "source_urls": {
            "callable": "https://www.yes.bank.in/personal-banking/yes-individual/deposits/fixed-deposit",
            "non_callable": "https://www.yes.bank.in/pdf?name=bulk_fixed_deposit_interest_rates_v1_pdf.pdf",
        },
    },
    "idfc": {
        "name": "IDFC First Bank",
        "source_urls": {
            "callable": "https://www.idfcfirst.bank.in/interest-rate",
            "non_callable": "https://www.idfcfirst.bank.in/interest-rate",
        },
    },
    "icici": {
        "name": "ICICI Bank",
        "source_urls": {
            "callable": "https://www.icici.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates",
            "non_callable": "https://www.icici.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates",
        },
    },
    "axis": {
        "name": "Axis Bank",
        # Stable landing page (dated PDF filenames change when rates update).
        "source_urls": {
            "callable": "https://www.axis.bank.in/deposits/fixed-deposits/fd-interest-rates",
            "non_callable": "https://www.axis.bank.in/deposits/fixed-deposits/fd-interest-rates",
        },
    },
    "sbi": {
        "name": "State Bank of India",
        "source_urls": {
            "callable": "https://sbi.bank.in/web/interest-rates/deposit-rates/retail-domestic-term-deposits",
            "non_callable": "https://sbi.bank.in/web/interest-rates/deposit-rates/retail-domestic-term-deposits",
        },
    },
    "indusind": {
        "name": "IndusInd Bank",
        "source_urls": {
            "callable": "https://www.indusind.bank.in/in/en/personal/rates.html",
            "non_callable": "https://www.indusind.bank.in/in/en/personal/rates.html",
        },
    },
    "hdfc": {
        "name": "HDFC Bank",
        "source_urls": {
            "callable": "https://www.hdfc.bank.in/interest-rates",
            "non_callable": "https://www.hdfc.bank.in/interest-rates",
        },
    },
    "cub": {
        "name": "City Union Bank",
        "source_urls": {
            "callable": "https://cityunionbank.bank.in/deposit-interest-rate",
            "non_callable": "https://cityunionbank.bank.in/deposit-interest-rate",
        },
    },
}


def get_source_url(bank_slug: str, fd_type: str) -> str:
    """Return the official bank page/PDF URL for a given FD type."""
    meta = BANKS.get(bank_slug, {})
    urls = meta.get("source_urls", {})
    return urls.get(fd_type, urls.get("callable", ""))


def all_bank_slugs() -> list[str]:
    """Bank order used by the UI and scrape runner."""
    return list(BANKS.keys())
