"""
Live FD rate scrapers from official bank websites.

Each scrape_*() function:
  1. Downloads HTML / PDF / JSON from the bank
  2. Parses tenor bands + rates exactly as published
  3. Returns bank-native tenure labels (not remapped to a shared grid)

Return shape for every bank:
  {
    "callable": { "<bank tenure text>": {"<3 crore": Decimal, ...}, ... },
    "non_callable": { ... },
  }
Only published slabs are present; missing slabs are omitted (UI shows '—').
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from decimal import Decimal

import requests
from bs4 import BeautifulSoup
try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Playwright is optional.
    sync_playwright = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from bank_data import get_source_url

# Pretend to be a normal browser so bank sites do not block the request.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

@dataclass
class TenorBand:
    """One tenor range + rates scraped from a bank page/PDF."""

    label: str
    min_days: int
    max_days: int
    under_3cr: Decimal | None = None
    three_to_5cr: Decimal | None = None


def _pct(value: str | None) -> Decimal | None:
    """Parse '6.75%' / '6.75' into Decimal, or None if not a rate."""
    if not value:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(value).replace(",", ""))
    if not m:
        return None
    return Decimal(m.group(1)).quantize(Decimal("0.01"))


def _fetch(url: str) -> str:
    """Simple HTTP GET returning HTML/text."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def _fetch_rendered(url: str) -> str:
    """Load a JS-rendered page with Playwright (fallback for dynamic sites)."""
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed in this environment")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Let dynamic tables settle.
        page.wait_for_timeout(1500)
        html = page.content()
        page.close()
        browser.close()
    return html


def _months_to_days(months: float) -> int:
    return int(round(months * 30.4375))


def parse_tenor_range(tenor: str) -> tuple[int, int]:
    """Best-effort parse of bank tenure text into day range."""
    t = tenor.strip().lower().replace("–", "-").replace("—", "-")
    t = re.sub(r"\s+", " ", t)

    if m := re.match(r"^(\d+)\s*days?\s*[-–]\s*(\d+)\s*days?$", t):
        return int(m.group(1)), int(m.group(2))
    if m := re.match(r"^(\d+)\s*days?\s*[-–]\s*(\d+)\s*years?$", t):
        return int(m.group(1)), int(m.group(2)) * 365
    if m := re.match(r"^(\d+)\s*days?$", t):
        d = int(m.group(1))
        return d, d
    if m := re.match(r"^(\d+)\s*years?$", t):
        d = int(m.group(1)) * 365
        return d, d
    if "1 year to below 1 year 6 month" in t:
        return 365, _months_to_days(18) - 1
    if "1 year 6 months to below 1 year 7 months" in t:
        return _months_to_days(18), _months_to_days(19) - 1
    if "1 year 7 months to below 2 years" in t:
        return _months_to_days(19), 729
    if "1 year 7 months to 3 years" in t:
        return _months_to_days(19), 1095
    if "2 years to less than 3 year" in t:
        return 730, 1094
    if "2 years to 3 years" in t:
        return 730, 1095
    if "1 year to less than 2 years" in t:
        return 365, 729
    if "above 3 years up to below 61 months" in t or "above 3 years to below 61 months" in t:
        return 1096, _months_to_days(61) - 1
    if "61 months and above" in t:
        return _months_to_days(61), 99999
    if "270 days to 364 days" in t:
        return 270, 364
    if "355 days to 364 days" in t:
        return 355, 364
    if "211 days to 364 days" in t:
        return 211, 364
    if "211 days to 269 days" in t:
        return 211, 269
    if "1 year 6 months to below 1 year 7 months" in t:
        return _months_to_days(18), _months_to_days(19) - 1
    if "1 year 7 months to below 2 years" in t:
        return _months_to_days(19), 729
    if "2 years to 3 years" in t:
        return 730, 1095
    if "above 3 years" in t and "61 months" in t:
        return 1096, _months_to_days(61) - 1
    if "1 year to below 1 year 1 month" in t:
        return 365, _months_to_days(13) - 1
    if "1 year 1 month to 3 years" in t:
        return _months_to_days(13), 1095
    if "1 year to 1 year 10 days" in t:
        return 365, 375
    if "18 months < 2 years" in t or "18 months to < 2 years" in t:
        return _months_to_days(18), 729
    if "1 year" == t.strip() or t == "1 year ":
        return 365, 365
    if "1 year 1 day" in t and "370 days" in t:
        return 366, 370
    if "371 days" in t and "390 days" in t:
        return 371, 390
    if "391 days" in t and "499 days" in t:
        return 391, 499
    if "500 days" in t and "3 years" in t:
        return 500, 1095
    if "1 year to < 15 months" in t:
        return 365, _months_to_days(15) - 1
    if "15 months to < 18 months" in t:
        return _months_to_days(15), _months_to_days(18) - 1
    if "18 months to < 21 months" in t:
        return _months_to_days(18), _months_to_days(21) - 1
    if "18 months to 2 years" in t:
        return _months_to_days(18), 730
    if "21 months to 2 years" in t:
        return _months_to_days(21), 730
    if (
        "2 year 1 day to 3 years" in t
        or "2 years 1 day to 3 years" in t
        or "2 years 1 day to < 2 year 11 months" in t
    ):
        return 731, 1095
    if "2 years 11 months (35 months)" in t:
        d = _months_to_days(35)
        return d, d
    if "4 year 7 months (55 months)" in t:
        d = _months_to_days(55)
        return d, d
    if "3 years 1 day" in t:
        return 1096, 1825
    if "5 years 1 day to 10 years" in t:
        return 1826, 3650
    if "181 days" in t and "less than 1 year" in t:
        return 181, 364
    if "270 days" in t and "364 days" in t:
        return 270, 364
    if "355 days" in t and "364 days" in t:
        return 355, 364
    if "1 year to below 1 year 1 month" in t:
        return 365, _months_to_days(13) - 1
    if "1 year 1 month to below 1 year 6 months" in t:
        return _months_to_days(13), _months_to_days(18) - 1
    if "1 year to 389 days" in t:
        return 365, 389
    if "390 days to < 15 months" in t:
        return 390, _months_to_days(15) - 1
    if "390 days to < 18 months" in t:
        return 390, _months_to_days(18) - 1
    if "271 days to < 1 year" in t:
        return 271, 364
    # if "1 year to < 18 months" in t:
    #     return 365, _months_to_days(18) - 1
    if "15 months to < 18 months" in t:
        return _months_to_days(15), _months_to_days(18) - 1
    if "7 - 14 days" in t or "7-14 days" in t:
        return 7, 14
    if "15-29 days" in t or "15 - 29 days" in t:
        return 15, 29
    if "30-45 days" in t or "30 - 45 days" in t:
        return 30, 45
    if "46-60 days" in t or "46 - 60 days" in t:
        return 46, 60
    if "61-89 days" in t or "61 - 89 days" in t:
        return 61, 89
    if "90 days <=" in t and "6 months" in t:
        return 90, 182
    if "6 months 1 day <=" in t and "9 months" in t:
        return 183, 274
    if "9 months 1 day to < 1 year" in t:
        return 275, 364
    if "89 days <=" in t and "120" in t:
        return 89, 120
    if "121 days <=" in t and "150" in t:
        return 121, 150
    if "151 days <=" in t and "6 months" in t:
        return 151, 182
    if "6 months 1 day <=" in t and "9months" in t:
        return 183, 274
    if "2 year 1 day to 3 years" in t or "2 years 1 day to < 2 year 11 months" in t:
        return 731, 1095
    if "3 year 1 day to 5 years" in t or "3 years 1 day to 5 years" in t:
        return 1096, 1825
    if "5 year 1 day to 10 years" in t or "5 years 1 day to 10 years" in t:
        return 1826, 3650
    if "over 3 years upto 5 years" in t or "above 3 years to 10 years" in t:
        return 1096, 1825
    if "556 days to 3 years" in t or "556 days to 3 year" in t:
        return 556, 1095
    if "336 days to < 12 months" in t:
        return 336, _months_to_days(12) - 1
    if re.fullmatch(r"\d+\s*months?", t):
        months = int(re.match(r"(\d+)", t).group(1))
        days = _months_to_days(months)
        return days, days
    if "12 months 1 day < 18 months" in t:
        return 366, _months_to_days(18) - 1
    if "18 months 1 day < 24 months" in t:
        return _months_to_days(18) + 1, 729
    if "24 months < 35 months" in t:
        return 730, _months_to_days(35) - 1
    if "35 months 1 day to < 36 months" in t:
        return _months_to_days(35) + 1, _months_to_days(36) - 1
    if "36 months to < 60 months" in t:
        return _months_to_days(36), _months_to_days(60) - 1
    if "60 months 1 day to <= 120 months" in t:
        return _months_to_days(60) + 1, _months_to_days(120)
    if "12m (1 year)" in t or "12 m (1 year)" in t:
        return 365, 365
    if "12 m 1 d to <15m" in t:
        return 366, _months_to_days(15) - 1
    if "15m to 18m" in t:
        return _months_to_days(15), _months_to_days(18) - 1
    if "18m 1 d to < 24 m" in t:
        return _months_to_days(18) + 1, 729
    if "24 m to < 35 m" in t:
        return 730, _months_to_days(35) - 1
    if "35 month" in t:
        return _months_to_days(35), _months_to_days(35)

    # Fallback: extract first number as days/months/years
    nums = [int(x) for x in re.findall(r"(\d+)", t)]
    if not nums:
        return 0, 99999
    if "year" in t and len(nums) >= 2:
        return nums[0] * 365, nums[1] * 365
    if "year" in t:
        d = nums[0] * 365
        return d, d
    if "month" in t and len(nums) >= 2:
        return _months_to_days(nums[0]), _months_to_days(nums[1])
    if "day" in t and len(nums) >= 2:
        return nums[0], nums[1]
    if "day" in t:
        return nums[0], nums[0]
    return nums[0], nums[-1]


def pick_rate(bands: list[TenorBand], day: int, slab: str) -> Decimal | None:
    """
    Find the rate for a given day + slab.
    Prefers the narrowest matching tenor band when several overlap.
    """
    matches = [band for band in bands if band.min_days <= day <= band.max_days]
    if not matches:
        return None
    band = min(matches, key=lambda b: (b.max_days - b.min_days, b.min_days))
    return band.under_3cr if slab == "<3 crore" else band.three_to_5cr


def to_native_format(
    callable_bands: list[TenorBand],
    non_callable_bands: list[TenorBand] | None = None,
) -> dict[str, dict[str, dict[str, Decimal]]]:
    """Keep bank tenure labels as published (one row per bank tenor band)."""
    if non_callable_bands is None:
        non_callable_bands = callable_bands

    def _build(bands: list[TenorBand]) -> dict[str, dict[str, Decimal]]:
        out: dict[str, dict[str, Decimal]] = {}
        for band in bands:
            slabs: dict[str, Decimal] = {}
            if band.under_3cr is not None:
                slabs["<3 crore"] = band.under_3cr
            if band.three_to_5cr is not None:
                slabs["3 Cr < 5 Cr"] = band.three_to_5cr
            if slabs:
                out[band.label] = slabs
        return out

    return {
        "callable": _build(callable_bands),
        "non_callable": _build(non_callable_bands),
    }


def to_native_from_slab_tables(
    lt3_bands: list[TenorBand],
    slab_35_bands: list[TenorBand] | None = None,
) -> dict[str, dict[str, Decimal]]:
    """
    Merge separate <3 Cr and 3–5 Cr bank tables using each bank's own tenure text.
    When 3–5 Cr bands overlap a <3 Cr tenor, rates share that row; otherwise a
    new row is added with the 3–5 Cr bank label.
    """
    rows: dict[str, dict[str, Decimal]] = {}

    for band in lt3_bands:
        slabs: dict[str, Decimal] = {}
        if band.under_3cr is not None:
            slabs["<3 crore"] = band.under_3cr
        if band.three_to_5cr is not None:
            slabs["3 Cr < 5 Cr"] = band.three_to_5cr
        if slabs:
            rows[band.label] = slabs

    if not slab_35_bands:
        return rows

    for band in slab_35_bands:
        rate = band.three_to_5cr if band.three_to_5cr is not None else band.under_3cr
        if rate is None:
            continue
        mid = (band.min_days + band.max_days) // 2
        match_label = None
        for lt in lt3_bands:
            if lt.min_days <= mid <= lt.max_days:
                match_label = lt.label
                break
        label = match_label or band.label
        if label not in rows:
            rows[label] = {}
        rows[label]["3 Cr < 5 Cr"] = rate

    return rows


# Backwards-compatible aliases (older call sites / docs).
to_cub_format = to_native_format
to_cub_from_slab_tables = to_native_from_slab_tables


def _parse_rate_table_rows(
    table,
    rate_col: int = 1,
    *,
    three_to_5: bool = False,
) -> list[TenorBand]:
    bands: list[TenorBand] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) <= rate_col:
            continue
        tenor = cells[0]
        if not re.search(r"\d", tenor):
            continue
        if any(k in tenor.lower() for k in ("tenure", "period", "bucket", "applicable")):
            continue
        if cells[rate_col].strip().upper() in {"NA", "--", "-"}:
            continue
        rate = _pct(cells[rate_col])
        if rate is None:
            continue
        min_d, max_d = parse_tenor_range(tenor)
        if three_to_5:
            bands.append(TenorBand(tenor, min_d, max_d, three_to_5cr=rate))
        else:
            bands.append(TenorBand(tenor, min_d, max_d, under_3cr=rate))
    return bands


def _find_table(soup: BeautifulSoup, *markers: str, require: str | None = None) -> object | None:
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        lower = text.lower()
        if not all(marker.lower() in lower for marker in markers):
            continue
        if require and require.lower() not in lower:
            continue
        return table
    return None


def scrape_hdfc() -> dict:
    """HDFC: HTML interest-rates page — callable <3 Cr / 3–5 Cr + non-withdrawable."""
    html = _fetch(get_source_url("hdfc", "callable"))
    soup = BeautifulSoup(html, "html.parser")

    callable_lt3_table = _find_table(soup, "< 3 crore", "tenure bucket")
    callable_35_table = _find_table(soup, ">=3 crore", "5 crores")
    non_callable_table = _find_table(soup, "non withdrawable", "2 crore")

    if not callable_lt3_table:
        raise RuntimeError("No HDFC callable <3 Cr FD table found")

    callable_lt3 = _parse_rate_table_rows(callable_lt3_table, rate_col=1)
    callable_35 = (
        _parse_rate_table_rows(callable_35_table, rate_col=1, three_to_5=True)
        if callable_35_table
        else []
    )
    non_callable_35 = (
        _parse_rate_table_rows(non_callable_table, rate_col=1, three_to_5=True)
        if non_callable_table
        else []
    )

    return {
        "callable": to_cub_from_slab_tables(callable_lt3, callable_35 or None),
        "non_callable": to_cub_from_slab_tables([], non_callable_35 or None),
    }


CUB_DEPOSIT_URL = get_source_url("cub", "callable")


def scrape_cub() -> dict:
    """CUB: deposit-interest-rate page — both FD types and both slabs."""
    soup = BeautifulSoup(_fetch(CUB_DEPOSIT_URL), "html.parser")

    callable_lt3_table = _find_table(soup, "domestic/nro callable term deposit")
    callable_35_table = _find_table(
        soup, "callable bulk deposit", require="365 days to 443 days"
    )
    non_call_lt3_table = _find_table(soup, "non-callable deposit above 1 cr and below 3 cr")
    non_call_35_table = _find_table(
        soup, "non callable bulk deposit", require="365 days to 443 days"
    )

    if not callable_lt3_table:
        raise RuntimeError("No CUB callable FD table found")

    return {
        "callable": to_cub_from_slab_tables(
            _parse_rate_table_rows(callable_lt3_table, rate_col=1),
            _parse_rate_table_rows(callable_35_table, rate_col=1, three_to_5=True)
            if callable_35_table
            else None,
        ),
        "non_callable": to_cub_from_slab_tables(
            _parse_rate_table_rows(non_call_lt3_table, rate_col=1) if non_call_lt3_table else [],
            _parse_rate_table_rows(non_call_35_table, rate_col=1, three_to_5=True)
            if non_call_35_table
            else None,
        ),
    }


IDFC_INTEREST_RATE_URL = get_source_url("idfc", "callable")
IDFC_FD_API_URL = (
    "https://www.idfcfirst.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates"
)
IDFC_RETAIL_PDF_FALLBACK = (
    "https://www.idfcfirst.bank.in/content/dam/idfcfirstbank/interest-rate/"
    "Interest-Rates-on-Retail-Deposits-10th-June-2026.pdf"
)
IDFC_BULK_PDF_FALLBACK = (
    "https://www.idfcfirst.bank.in/content/dam/idfcfirstbank/interest-rate/"
    "Interest-rates-on-deposits-Rs-3-crs-and-above-wef-01072026.pdf"
)


def _idfc_discover_pdf_urls(html: str) -> tuple[str | None, str | None]:
    retail_url: str | None = None
    bulk_url: str | None = None
    base = "https://www.idfcfirst.bank.in"
    for match in re.findall(
        r"(?:https?://www\.idfcfirst\.bank\.in)?(/content/dam/idfcfirstbank/interest-rate/[^\"'\s>]+\.pdf)",
        html,
        re.I,
    ):
        url = match if match.startswith("http") else base + match
        low = url.lower()
        if "retail-deposits" in low:
            retail_url = url
        elif "3-crs-and-above" in low or "3-crs" in low:
            bulk_url = url
    return retail_url, bulk_url


def _parse_idfc_retail_pdf(text: str) -> list[TenorBand]:
    bands: list[TenorBand] = []
    line_re = re.compile(r"^(.+?)\s+(\d+(?:\.\d+)?)%")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "tax saver" in line.lower() or "green deposit" in line.lower():
            continue
        if "recurring deposit" in line.lower():
            break
        match = line_re.match(line)
        if not match:
            continue
        tenor = match.group(1).strip().rstrip("–").strip()
        if not re.search(r"\d", tenor):
            continue
        if not any(k in tenor.lower() for k in ("day", "month", "year")):
            continue
        rate = _pct(match.group(2))
        if rate is None:
            continue
        min_d, max_d = parse_tenor_range(tenor)
        bands.append(TenorBand(tenor, min_d, max_d, under_3cr=rate))
    return bands


def _parse_idfc_bulk_pdf(
    text: str,
) -> tuple[list[TenorBand], list[TenorBand]]:

    non_callable_bands = []

    # We ONLY want:
    # Section I:
    # Rs. 3 crore to 27.50 crore
    # Premature withdrawal NOT permitted
    #
    # And specifically the first rate column:
    # Rs. 3 crore - 5 crore

    section_1 = False

    line_re = re.compile(
        r"^(.+?)\s+(\d+(?:\.\d+)?)%"
    )

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        lower = line.lower()

        # -----------------------------------------
        # START SECTION I
        # -----------------------------------------

        if (
            "premature withdrawal is not permitted"
            in lower
            and "rs. 3 crore to 27.50 crore"
            in lower
        ):
            section_1 = True
            continue

        # -----------------------------------------
        # STOP at Section II
        # -----------------------------------------

        if section_1 and (
            "premature withdrawal is permitted"
            in lower
        ):
            break

        # -----------------------------------------
        # Only process Section I
        # -----------------------------------------

        if not section_1:
            continue

        match = line_re.match(line)

        if not match:
            continue

        tenor = match.group(1).strip()

        rate_text = match.group(2)

        # Ignore unwanted rows
        if "tax saver" in tenor.lower():
            continue

        if "green" in tenor.lower():
            continue

        if not re.search(r"\d", tenor):
            continue

        rate = _pct(rate_text)

        if rate is None:
            continue

        min_d, max_d = parse_tenor_range(tenor)

        non_callable_bands.append(
            TenorBand(
                label=tenor,
                min_days=min_d,
                max_days=max_d,
                three_to_5cr=rate,
            )
        )

    return [], non_callable_bands




def _parse_idfc_fd_api_table(html: str) -> list[TenorBand]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table(soup, "less than", "3 crore")
    if not table:
        return []
    return _parse_rate_table_rows(table, rate_col=1)


def scrape_idfc() -> dict:
    """IDFC: interest-rate PDFs (retail + bulk) with HTML FD table fallback."""
    interest_html = _fetch(IDFC_INTEREST_RATE_URL)
    retail_pdf_url, bulk_pdf_url = _idfc_discover_pdf_urls(interest_html)
    retail_pdf_url = retail_pdf_url or IDFC_RETAIL_PDF_FALLBACK
    bulk_pdf_url = bulk_pdf_url or IDFC_BULK_PDF_FALLBACK

    callable_lt3 = _parse_idfc_retail_pdf(_fetch_pdf_text(retail_pdf_url))
    if not callable_lt3:
        callable_lt3 = _parse_idfc_fd_api_table(_fetch(IDFC_FD_API_URL))
    bulk_text = _fetch_pdf_text(bulk_pdf_url)
    callable_35, non_callable_35 = _parse_idfc_bulk_pdf(bulk_text)

    if not callable_lt3:
        raise RuntimeError("No IDFC callable FD rates found")
    if not callable_35 and not non_callable_35:
        raise RuntimeError("No IDFC bulk (3+ Cr) FD rates found in PDF")

    return {
        "callable": to_cub_from_slab_tables(callable_lt3, callable_35 or None),
        "non_callable": to_cub_from_slab_tables([], non_callable_35 or None),
    }


def _fetch_pdf_bytes_text(content: bytes) -> str:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required for PDF rate sources")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _fetch_pdf_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return _fetch_pdf_bytes_text(response.content)

# ------------------------------------------------------------------------------
AXIS_FD_RATES_PAGE = get_source_url("axis", "callable")
# Used only if the landing page has no PDF links (site redesign / downtime).
AXIS_CALLABLE_PDF_FALLBACK = (
    "https://www.axis.bank.in/docs/default-source/default-document-library/"
    "interest-rates/domestic-fixed-deposits-11-july-26.pdf"
)
AXIS_NON_CALLABLE_PDF_FALLBACK = (
    "https://www.axis.bank.in/docs/default-source/default-document-library/"
    "interest-rates/domestic-fixed-deposits-plus-11-july-26.pdf"
)


def _axis_discover_pdf_urls(html: str) -> tuple[str | None, str | None]:
    """
    Find current Domestic FD / FD Plus PDF links on the Axis rates page.

    Axis renames PDFs when rates change (e.g. ...-11-july-26.pdf); the HTML page
    always points at the latest files.
    """
    call_url: str | None = None
    nc_url: str | None = None
    base = "https://www.axis.bank.in"
    pattern = (
        r"(?:https?://(?:www\.)?axis\.bank\.in)?"
        r"(/docs/default-source/default-document-library/interest-rates/"
        r"domestic-fixed-deposits[^\"'\s>]+\.pdf(?:\?[^\"'\s>]*)?)"
    )
    for path in re.findall(pattern, html, re.I):
        url = path if path.startswith("http") else base + path
        low = path.lower()
        if "domestic-fixed-deposits-plus" in low:
            nc_url = url
        elif re.search(r"domestic-fixed-deposits-[^/]+\.pdf", low):
            call_url = url
    return call_url, nc_url


def _parse_axis_pdf(text: str, *, non_callable: bool = False) -> list[TenorBand]:
    """Parse Axis Bank FD PDF (callable or FD Plus non-callable)."""
    bands: list[TenorBand] = []
    active = False
     # Separate the tenure from the rate columns.
    tenor_re = re.compile(
        r"^(.*\b(?:days?|months?|years?)\b)\s+(.+)$",
        re.IGNORECASE,
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if non_callable:
            if "fixed deposits plus" in lower:
                active = True
                continue
        elif "deposits - less than" in lower:
            active = True
            continue

        if not active:
            continue
        if lower.startswith("disclaimer") or "deposits general" in lower or "senior citizens -" in lower:
            break

       
        match = tenor_re.match(line)
        if not match:
            continue

        tenor = match.group(1).strip()
        rate_text = match.group(2).strip()

        # Skip section title lines, not real tenor rows.
        if "maturity" in tenor.lower():
            continue
        if tenor.lower().startswith("deposits") and "less than" in tenor.lower():
            continue

        # Extract the rate columns AFTER the tenure.
        rates = re.findall(r"\d+(?:\.\d+)?", rate_text)

        if not rates:
            continue

        # ============================================================
        # FD PLUS / NON-CALLABLE
        # First rate = 3 Cr < 5 Cr
        # Do NOT take the later 5 Cr < 10 Cr / 10 Cr < 25 Cr rates.
        # ============================================================
        if non_callable:
            three = _pct(rates[0])

            if three is None:
                continue

            min_d, max_d = parse_tenor_range(tenor)

            bands.append(
                TenorBand(
                    tenor,
                    min_d,
                    max_d,
                    three_to_5cr=three,
                )
            )
            continue

        # ============================================================
        # CALLABLE
        # First rate = <3 Cr
        # Second rate = 3 Cr < 5 Cr
        # ============================================================
        if len(rates) < 2:
            continue

        under = _pct(rates[0])
        three = _pct(rates[1])

        if under is None:
            continue

        min_d, max_d = parse_tenor_range(tenor)

        bands.append(
            TenorBand(
                tenor,
                min_d,
                max_d,
                under_3cr=under,
                three_to_5cr=three,
            )
        )

    return bands


def scrape_axis() -> dict:
    """Axis: discover dated PDFs from the FD rates page, then parse with pdfplumber."""
    html = _fetch(AXIS_FD_RATES_PAGE)
    call_url, nc_url = _axis_discover_pdf_urls(html)
    call_url = call_url or AXIS_CALLABLE_PDF_FALLBACK
    nc_url = nc_url or AXIS_NON_CALLABLE_PDF_FALLBACK

    callable_bands = _parse_axis_pdf(_fetch_pdf_text(call_url), non_callable=False)
    non_callable_bands = _parse_axis_pdf(_fetch_pdf_text(nc_url), non_callable=True)
    if not callable_bands and not non_callable_bands:
        raise RuntimeError("No Axis FD rates found in PDF sources")
    return to_cub_format(callable_bands, non_callable_bands)


INDUSIND_RATES_URL = "https://www.indusind.bank.in/in/en/personal/rates.html"


def _indusind_table_context(table) -> str:
    prev = ""
    for el in table.find_all_previous(["h1", "h2", "h3", "h4", "p", "strong"], limit=8):
        prev = el.get_text(" ", strip=True) + " " + prev
    return (prev + " " + table.get_text(" ", strip=True)[:400]).lower()


def _indusind_data_row_count(table) -> int:
    count = 0
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) >= 2 and re.search(r"\d", cells[0]):
            count += 1
    return count


def _indusind_header_text(table) -> str:
    first = table.find("tr")
    if not first:
        return ""
    return " ".join(c.get_text(" ", strip=True) for c in first.find_all(["td", "th"])).lower()


# def _parse_indusind_rate_table(
#     table,
#     rate_col: int = 1,
#     *,
#     three_to_5: bool = False,
# ) -> list[TenorBand]:
#     bands: list[TenorBand] = []
#     for tr in table.find_all("tr"):
#         cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
#         if len(cells) <= rate_col:
#             continue
#         tenor = cells[0]
#         if "tenure" in tenor.lower() or not re.search(r"\d", tenor):
#             continue
#         if "tax saver" in tenor.lower():
#             continue
#         rate = _pct(cells[rate_col])
#         if rate is None:
#             continue
#         min_d, max_d = parse_tenor_range(tenor)
#         if three_to_5:
#             bands.append(TenorBand(tenor, min_d, max_d, three_to_5cr=rate))
#         else:
#             bands.append(TenorBand(tenor, min_d, max_d, under_3cr=rate))
#     return bands

def _parse_indusind_rate_table(
    table,
    rate_col: int = 1,
    *,
    three_to_5: bool = False,
) -> list[TenorBand]:
    bands: list[TenorBand] = []

    for tr in table.find_all("tr"):
        cells = [
            c.get_text(" ", strip=True)
            for c in tr.find_all(["td", "th"])
        ]

        if len(cells) <= rate_col:
            continue

        tenor = cells[0].strip()
        tenor_lower = tenor.lower()

        # Skip headers / invalid rows
        if "tenure" in tenor_lower:
            continue

        if not re.search(r"\d", tenor):
            continue

        if "tax saver" in tenor_lower:
            continue

        rate = _pct(cells[rate_col])

        if rate is None:
            continue

        min_d, max_d = parse_tenor_range(tenor)

        if three_to_5:
            bands.append(
                TenorBand(
                    tenor,
                    min_d,
                    max_d,
                    three_to_5cr=rate,
                )
            )
        else:
            bands.append(
                TenorBand(
                    tenor,
                    min_d,
                    max_d,
                    under_3cr=rate,
                )
            )

    return bands


# def scrape_indusind() -> dict:
#     """IndusInd: rates.html tables classified by premature-withdrawal headers."""
#     html = _fetch(INDUSIND_RATES_URL)
#     soup = BeautifulSoup(html, "html.parser")

#     callable_lt3: list[TenorBand] = []
#     callable_35: list[TenorBand] = []
#     non_call_lt3: list[TenorBand] = []
#     non_call_35: list[TenorBand] = []

#     for table in soup.find_all("table"):
#         if _indusind_data_row_count(table) < 5:
#             continue

#         ctx = _indusind_table_context(table)
#         txt = table.get_text(" ", strip=True).lower()
#         hdr = _indusind_header_text(table)
#         if "tenure" not in ctx and "tenure" not in txt:
#             continue

#         label_text = f"{ctx} {hdr}"
#         is_non_call = "premature withdrawal not allowed" in label_text
#         is_call = "premature withdrawal allowed" in label_text and not is_non_call
#         is_lt3_call = (
#             ("< 3 cr" in hdr or "< 3 cr" in txt)
#             and "above 1 crore" not in hdr
#             and "3 crore to less than 5" not in hdr
#         )
#         is_35_call = "3 crore to less than 5" in hdr and not is_non_call
#         is_nc_lt3 = "above 1 crore to less than 3" in hdr and is_non_call
#         is_35_nc = "3 crore to less than 5" in hdr and is_non_call

#         if is_call and is_lt3_call:
#             callable_lt3 = _parse_indusind_rate_table(table)
#         elif is_call and is_35_call:
#             callable_35 = _parse_indusind_rate_table(table, three_to_5=True)
#         elif is_nc_lt3:
#             non_call_lt3 = _parse_indusind_rate_table(table)
#         elif is_35_nc:
#             non_call_35 = _parse_indusind_rate_table(table, three_to_5=True)

#     if not callable_lt3 and not non_call_lt3:
#         raise RuntimeError("No IndusInd FD rate tables found")

#     return {
#         "callable": to_cub_from_slab_tables(callable_lt3, callable_35 or None),
#         "non_callable": to_cub_from_slab_tables(non_call_lt3, non_call_35 or None),
#     }

def scrape_indusind() -> dict:
    """
    IndusInd FD rates.

    Important:
    Select the correct table based on:
      1. ₹3 Cr to less than ₹5 Cr
      2. Premature Withdrawal Allowed / Not Allowed

    This prevents one ₹3 Cr–₹5 Cr table from overwriting another.
    """

    html = _fetch(INDUSIND_RATES_URL)
    soup = BeautifulSoup(html, "html.parser")

    callable_lt3: list[TenorBand] = []
    callable_35: list[TenorBand] = []

    non_call_lt3: list[TenorBand] = []
    non_call_35: list[TenorBand] = []

    # ---------------------------------------------------------
    # Find all IndusInd FD tables
    # ---------------------------------------------------------
    for table in soup.find_all("table"):

        # Ignore small/non-rate tables
        if _indusind_data_row_count(table) < 5:
            continue

        ctx = _indusind_table_context(table)
        txt = table.get_text(" ", strip=True).lower()
        hdr = _indusind_header_text(table)

        # Need a tenure column/table
        if "tenure" not in ctx and "tenure" not in txt:
            continue

        label_text = f"{ctx} {hdr}".lower()

        # Normalize spaces
        label_text = re.sub(r"\s+", " ", label_text)

        # ---------------------------------------------------------
        # Detect premature withdrawal type
        # ---------------------------------------------------------
        is_non_call = (
            "premature withdrawal not allowed" in label_text
            or "premature withdrawal is not allowed" in label_text
        )

        is_call = (
            (
                "premature withdrawal allowed" in label_text
                or "premature withdrawal is allowed" in label_text
            )
            and not is_non_call
        )

        # ---------------------------------------------------------
        # Detect amount slab
        # ---------------------------------------------------------

        # < 3 Cr / 1 Cr to < 3 Cr
        is_lt3 = (
            "< 3 cr" in label_text
            or "less than 3 cr" in label_text
            or "less than 3 crore" in label_text
        )

        # ₹3 Cr to < ₹5 Cr
        is_35 = bool(
            re.search(
                r"3\s*crore\s+to\s+less\s+than\s+5",
                label_text,
                re.IGNORECASE,
            )
            or re.search(
                r"3\s*cr\s+to\s+less\s+than\s+5",
                label_text,
                re.IGNORECASE,
            )
        )

        # ---------------------------------------------------------
        # CALLABLE: ₹3 Cr < ₹5 Cr
        # ---------------------------------------------------------
        if is_call and is_35:

            parsed = _parse_indusind_rate_table(
                table,
                rate_col=1,
                three_to_5=True,
            )

            # Only accept a real rate table
            if parsed:
                callable_35 = parsed

                # We found the required table.
                # Do not allow another table to overwrite it.
                continue

        # ---------------------------------------------------------
        # CALLABLE: < ₹3 Cr
        # ---------------------------------------------------------
        if is_call and is_lt3 and not is_35:

            parsed = _parse_indusind_rate_table(
                table,
                rate_col=1,
                three_to_5=False,
            )

            if parsed:
                callable_lt3 = parsed

        # ---------------------------------------------------------
        # NON-CALLABLE: < ₹3 Cr
        # ---------------------------------------------------------
        elif is_non_call and is_lt3 and not is_35:

            parsed = _parse_indusind_rate_table(
                table,
                rate_col=1,
                three_to_5=False,
            )

            if parsed:
                non_call_lt3 = parsed

        # ---------------------------------------------------------
        # NON-CALLABLE: ₹3 Cr < ₹5 Cr
        # ---------------------------------------------------------
        elif is_non_call and is_35:

            parsed = _parse_indusind_rate_table(
                table,
                rate_col=1,
                three_to_5=True,
            )

            if parsed:
                non_call_35 = parsed

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------
    if not callable_lt3 and not non_call_lt3:
        raise RuntimeError(
            "No IndusInd FD rate tables found"
        )

    # ---------------------------------------------------------
    # Return final structure
    # ---------------------------------------------------------
    return {
        "callable": to_cub_from_slab_tables(
            callable_lt3,
            callable_35 or None,
        ),

        "non_callable": to_cub_from_slab_tables(
            non_call_lt3,
            non_call_35 or None,
        ),
    }

ICICI_PERSONAL_FD_URL = (
    "https://www.icici.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates"
)
ICICI_FD_JSON_URL = (
    "https://www.icici.bank.in/content/dam/icicibank-revamp/deposits/"
    "fixed-deposits/json/fd-interest-rate.json"
)
# interestData indices on the personal FD JSON feed.
ICICI_CALLABLE_TABLE = 1
ICICI_NON_CALLABLE_TABLE = 5


def _icici_rate(value) -> Decimal | None:
    if value is None:
        return None
    rate = Decimal(str(value)).quantize(Decimal("0.01"))
    # Placeholder values in the summary table are 1.1%.
    if rate < Decimal("2.00"):
        return None
    return rate


def _icici_json_to_bands(rows: list[dict]) -> list[TenorBand]:
    bands: list[TenorBand] = []
    for row in rows:
        tenure = row.get("tenure", "")
        if not tenure or "tax saver" in tenure.lower():
            continue
        under = _icici_rate(row.get("c1"))
        three = _icici_rate(row.get("c3"))
        if under is None and three is None:
            continue
        min_d, max_d = parse_tenor_range(tenure)
        bands.append(TenorBand(tenure, min_d, max_d, under_3cr=under, three_to_5cr=three))
    return bands


def scrape_icici() -> dict:
    """ICICI: official JSON feed (callable + non-callable tables)."""
    payload = requests.get(ICICI_FD_JSON_URL, headers=HEADERS, timeout=30).json()
    tables = payload.get("interestData", [])
    if len(tables) <= ICICI_NON_CALLABLE_TABLE:
        raise RuntimeError("Unexpected ICICI FD JSON structure")

    callable_bands = _icici_json_to_bands(tables[ICICI_CALLABLE_TABLE])
    non_callable_bands = _icici_json_to_bands(tables[ICICI_NON_CALLABLE_TABLE])
    if not callable_bands and not non_callable_bands:
        raise RuntimeError("No ICICI FD rates found in JSON feed")
    return to_cub_format(callable_bands, non_callable_bands)


SBI_RETAIL_URL = get_source_url("sbi", "callable")
YES_CALLABLE_CONTENT_ID = "CORE615ED1421C994D62B5C3D99D2CEE9BCE"
YES_BULK_ASSET_ID = "CONTA391B2F09BF64C72BF6C2CD073F98131"
YES_BULK_PDF_NAME = "bulk_fixed_deposit_interest_rates_v1_pdf.pdf"
YES_CONTENT_API = "https://www.yes.bank.in/sites/web/content/published/api/v1.1"


def _yes_channel_token() -> str:
    shell = _fetch(get_source_url("yes_bank", "non_callable"))
    match = re.search(r'siteToken"\s*:\s*"([a-f0-9]{32})"', shell, re.I)
    if not match:
        raise RuntimeError("Yes Bank channel token not found")
    return match.group(1)


def _yes_fetch_content_table(content_id: str) -> str:
    token = _yes_channel_token()
    url = f"{YES_CONTENT_API}/items/{content_id}?channelToken={token}"
    payload = requests.get(url, headers=HEADERS, timeout=30).json()
    table_html = (payload.get("fields") or {}).get("table")
    if not table_html:
        raise RuntimeError(f"Yes Bank content table missing for {content_id}")
    return table_html


def _yes_fetch_bulk_pdf_bytes() -> bytes:
    token = _yes_channel_token()
    url = (
        f"{YES_CONTENT_API}/assets/{YES_BULK_ASSET_ID}/native/{YES_BULK_PDF_NAME}"
        f"?download=false&channelToken={token}"
    )
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    if response.content[:4] != b"%PDF":
        raise RuntimeError("Yes Bank bulk FD PDF download failed")
    return response.content


def _parse_yes_callable_table(table_html: str) -> list[TenorBand]:
    """Parse every published Yes Bank callable <3 Cr tenure row from the CMS table."""
  
        # Convert HTML into a BeautifulSoup object
    soup = BeautifulSoup(
                table_html,
                "html.parser"
            )

    # Store the extracted FD bands
    bands: list[TenorBand] = []

    # Read every table row
    for tr in soup.find_all("tr"):

        # Extract only <td> cells
        cells = [
            c.get_text(" ", strip=True)
            for c in tr.find_all("td")
        ]

        # We need at least:
        # cells[0] = Period
        # cells[1] = Regular Interest Rate
        if len(cells) < 2:
            continue
        # --------------------------------------------------
        # PERIOD
        # --------------------------------------------------
        tenor = cells[0]

        tenor = " ".join(tenor.split())

        # --------------------------------------------------
        # REMOVE UNWANTED PERIODS
        # --------------------------------------------------

        if tenor in [
            "1 Year to < 18 Months",
            "18 Months to < 3 Years",
        ]:
            continue

        # --------------------------------------------------
        # CHECK VALID TENURE
        # --------------------------------------------------
        if not re.search(r"\d", tenor) or "period" in tenor.lower():
            continue
        
        # --------------------------------------------------
        # SKIP HEADER / SLAB ROWS
        # --------------------------------------------------

        if "crore" in tenor.lower() or "inr" in tenor.lower():
            continue
         # --------------------------------------------------
                # REGULAR INTEREST RATE
        # --------------------------------------------------
        
        under = _pct(cells[1])

       
        # No valid interest rate
        if under is None:
            continue

        # --------------------------------------------------
        # CONVERT TENURE TO DAYS
        # --------------------------------------------------
        min_d, max_d = parse_tenor_range(tenor)

        # --------------------------------------------------
        # SAVE RESULT
        # --------------------------------------------------

        bands.append(TenorBand(tenor, min_d, max_d, under_3cr=under))
    
    # Return all valid YES Bank FD rates
    return bands


def _parse_yes_bulk_pdf(text: str) -> tuple[list[TenorBand], list[TenorBand]]:
    """Parse 3–5 Cr callable and non-callable bands from the bulk FD PDF."""
    callable_bands: list[TenorBand] = []
    non_callable_bands: list[TenorBand] = []
    line_re = re.compile(r"^(.+?)\s+((?:\d+(?:\.\d+)?%\s*){6,})")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("tenure"):
            continue
        match = line_re.match(line)
        if not match:
            continue
        tenor = match.group(1).strip()
        if "senior" in tenor.lower() or "deposit" in tenor.lower():
            continue
        rates = [_pct(value) for value in re.findall(r"(\d+(?:\.\d+)?)%", match.group(2))]
        rates = [rate for rate in rates if rate is not None]
        if len(rates) < 6:
            continue
        min_d, max_d = parse_tenor_range(tenor)
        callable_bands.append(TenorBand(tenor, min_d, max_d, three_to_5cr=rates[2]))
        non_callable_bands.append(TenorBand(tenor, min_d, max_d, three_to_5cr=rates[5]))
    return callable_bands, non_callable_bands


def scrape_yes_bank() -> dict:
    """Yes Bank: CMS table for callable <3 Cr + bulk PDF for 3–5 Cr slabs."""
    callable_lt3 = _parse_yes_callable_table(_yes_fetch_content_table(YES_CALLABLE_CONTENT_ID))
    bulk_text = _fetch_pdf_bytes_text(_yes_fetch_bulk_pdf_bytes())
    callable_35, non_callable_35 = _parse_yes_bulk_pdf(bulk_text)
    if not callable_lt3:
        raise RuntimeError("No Yes Bank callable FD rates found")
    if not callable_35 and not non_callable_35:
        raise RuntimeError("No Yes Bank bulk (3–5 Cr) FD rates found in PDF")
    return {
        "callable": to_cub_from_slab_tables(callable_lt3, callable_35 or None),
        "non_callable": to_cub_from_slab_tables([], non_callable_35 or None),
    }


def scrape_sbi() -> dict:
    """SBI: retail domestic term deposit HTML (callable + limited non-callable)."""
    html = _fetch(SBI_RETAIL_URL)
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    callable_bands: list[TenorBand] = []
    non_callable_bands: list[TenorBand] = []

    if tables:
        for tr in tables[0].find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            tenor = cells[0]
            if "tenor" in tenor.lower() or not re.search(r"\d", tenor):
                continue
            revised_public = _pct(cells[2])
            if revised_public is None:
                continue
            min_d, max_d = parse_tenor_range(tenor)
            callable_bands.append(TenorBand(tenor, min_d, max_d, under_3cr=revised_public))

    if len(tables) > 1:
        for tr in tables[1].find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            tenor = cells[0]
            if "tenor" in tenor.lower() or not re.search(r"\d", tenor):
                continue
            if "card rate" in cells[2].lower():
                continue
            general_public = _pct(cells[2])
            if general_public is None:
                continue
            min_d, max_d = parse_tenor_range(tenor)
            non_callable_bands.append(TenorBand(tenor, min_d, max_d, under_3cr=general_public))

    if not callable_bands:
        raise RuntimeError("No SBI retail FD rates found")
    return to_cub_format(callable_bands, non_callable_bands or None)


# Registry: bank slug -> scrape function (used by scrapers.py / services.py).
SCRAPERS = {
    "yes_bank": scrape_yes_bank,
    "hdfc": scrape_hdfc,
    "cub": scrape_cub,
    "axis": scrape_axis,
    "idfc": scrape_idfc,
    "indusind": scrape_indusind,
    "icici": scrape_icici,
    "sbi": scrape_sbi,
}


def scrape_bank(slug: str) -> dict | None:
    """Run the live scraper for one bank slug, or return None if unknown."""
    fn = SCRAPERS.get(slug)
    if fn is None:
        return None
    return fn()
