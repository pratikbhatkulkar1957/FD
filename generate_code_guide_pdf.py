"""Generate FD Rates Tracker code explanation PDF."""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent / "FD_Rates_Code_Explanation.pdf"
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Body", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "FD Rates Tracker - Code Explanation", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Body", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "Confidential project documentation", align="C")


def add_title(pdf: PDF, text: str):
    pdf.set_font("Body", "B", 16)
    pdf.set_text_color(15, 76, 129)
    pdf.multi_cell(0, 9, text)
    pdf.ln(2)


def add_h2(pdf: PDF, text: str):
    pdf.ln(3)
    pdf.set_font("Body", "B", 12)
    pdf.set_text_color(20, 90, 150)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)


def add_h3(pdf: PDF, text: str):
    pdf.ln(2)
    pdf.set_font("Body", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6, text)
    pdf.ln(1)


def add_p(pdf: PDF, text: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Body", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 5.5, text)
    pdf.ln(1.5)


def add_bullet(pdf: PDF, text: str):
    pdf.set_x(pdf.l_margin + 4)
    pdf.set_font("Body", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(pdf.epw - 4, 5.5, f"- {text}")
    pdf.ln(0.5)


def add_code(pdf: PDF, text: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("Body", "", 9)
    pdf.set_text_color(25, 25, 25)
    pdf.multi_cell(0, 5, text, fill=True)
    pdf.ln(2)


def build():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("Body", "", FONT)
    pdf.add_font("Body", "B", FONT_B)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    # Cover
    pdf.ln(30)
    pdf.set_font("Body", "B", 24)
    pdf.set_text_color(15, 76, 129)
    pdf.cell(0, 12, "FD Rates Tracker", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Body", "B", 16)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 9, "Complete Code Explanation", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Body", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        6,
        "A guide to every Python module, database table, template, "
        "scraper, and API route in this project.",
        align="C",
    )
    pdf.set_x(pdf.l_margin)
    pdf.ln(16)
    pdf.set_font("Body", "", 10)
    pdf.cell(
        0,
        6,
        "Stack: FastAPI + Jinja2 + MySQL (Hostinger) + live bank scrapers",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        "Banks: Yes Bank, HDFC, CUB, Axis, IDFC, ICICI, SBI, IndusInd",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    # 1. Overview
    pdf.add_page()
    add_title(pdf, "1. What this project does")
    add_p(
        pdf,
        "This app scrapes Fixed Deposit (FD) interest rates from official Indian bank "
        "websites, stores them in MySQL, archives each scrape as JSON files, and shows "
        "them on a CUB-style dashboard. You can also compare best rates across banks "
        "and export CSV/Excel.",
    )
    add_h2(pdf, "Accuracy rule")
    add_p(
        pdf,
        "Only rates published by the bank are shown. If a bank does not publish a "
        "particular tenure/slab combination, the cell shows a dash (-). The app never "
        "guesses or copies rates from another slab.",
    )
    add_h2(pdf, "Standard table format (CUB style)")
    add_bullet(pdf, "FD types: Callable and Non-Callable")
    add_bullet(pdf, "Deposit slabs: <3 crore and 3 Cr < 5 Cr")
    add_bullet(
        pdf,
        "Tenures: 365-443 days, 444 days, 445-554 days, 555 days, 556 days to 3 Years",
    )

    # 2. Architecture
    add_title(pdf, "2. Architecture (how requests flow)")
    add_p(pdf, "When you open the dashboard or click Refresh Rates, this is the flow:")
    add_code(
        pdf,
        "Browser\n"
        "  -> main.py (FastAPI routes)\n"
        "    -> services.py (business logic / table building)\n"
        "      -> scrapers.py + rate_scrapers.py (fetch from bank sites)\n"
        "      -> db_storage.py (save/read MySQL)\n"
        "      -> scrape_archive.py (save JSON under data/scrapes/)\n"
        "  <- templates/*.html (HTML response)",
    )
    add_h2(pdf, "File map")
    add_bullet(pdf, "main.py - HTTP routes and app startup/shutdown")
    add_bullet(pdf, "config.py - settings loaded from .env")
    add_bullet(pdf, "bank_data.py - bank names, source URLs, tenure rows")
    add_bullet(pdf, "schemas.py - Pydantic models for API responses")
    add_bullet(pdf, "services.py - scrape orchestration + dashboard compare logic")
    add_bullet(pdf, "scrapers.py - converts raw scraper dicts into RatePoint objects")
    add_bullet(pdf, "rate_scrapers.py - one live scraper per bank")
    add_bullet(pdf, "db_storage.py - MySQL connection and queries")
    add_bullet(pdf, "scrape_archive.py - timestamped JSON archives")
    add_bullet(pdf, "schema.sql - MySQL table definitions")
    add_bullet(pdf, "templates/ - Jinja2 HTML pages")

    # 3. config
    add_title(pdf, "3. config.py - Settings")
    add_p(
        pdf,
        "Uses pydantic-settings. Values come from .env (MYSQL_HOST, MYSQL_USER, "
        "MYSQL_PASSWORD, MYSQL_DATABASE, etc.). Important flags:",
    )
    add_bullet(pdf, "INIT_DB_ON_STARTUP=false - do not run schema every start (Hostinger limits)")
    add_bullet(pdf, "SCRAPE_ON_STARTUP=false - scrape only when you click Refresh")
    add_bullet(pdf, "SCRAPES_DIR - folder for archived scrape sessions")
    add_bullet(pdf, "EXCEL_EXPORT_FILE - where Excel export is written")

    # 4. bank_data
    add_title(pdf, "4. bank_data.py - Master bank metadata")
    add_p(
        pdf,
        "Defines TENURE_ROWS (the 5 standard tenure bands), DEPOSIT_SLABS, and BANKS. "
        "Each bank has a slug (e.g. hdfc), display name, and source_urls for callable "
        "and non_callable pages/PDFs.",
    )
    add_p(
        pdf,
        "Helpers: get_source_url(slug, fd_type) returns the official URL shown under "
        "each table; all_bank_slugs() returns the bank order for the UI.",
    )

    # 5. schemas
    add_title(pdf, "5. schemas.py - Data shapes")
    add_bullet(pdf, "BankOut - slug + name for APIs")
    add_bullet(
        pdf,
        "RatePoint - one scraped cell (fd_type, tenure, slab, rate, source_url). "
        "Used when writing into MySQL.",
    )
    add_bullet(pdf, "RateOut / HistoryOut / BestRateOut - JSON response models")

    # 6. schema.sql
    add_title(pdf, "6. schema.sql - Database tables")
    add_h3(pdf, "banks")
    add_p(pdf, "Primary key: slug. Stores bank display name.")
    add_h3(pdf, "fd_rates (current rates)")
    add_p(
        pdf,
        "One row per bank + fd_type + tenure_label + deposit_slab (unique). "
        "Holds the latest rate_percent, tenure day range, sort_order, source_url, "
        "and updated_at.",
    )
    add_h3(pdf, "rate_history")
    add_p(
        pdf,
        "Append-only log of rate changes. When a scrape writes a new value that "
        "differs from the previous one, a history row is inserted.",
    )

    # 7. db_storage
    add_title(pdf, "7. db_storage.py - MySQL layer")
    add_p(
        pdf,
        "All database access goes through this file. Hostinger shared MySQL has a "
        "strict connection-per-hour limit, so the code keeps ONE reused connection "
        "(_get_connection) protected by a threading lock.",
    )
    add_h2(pdf, "Key functions")
    add_bullet(pdf, "init_db() - runs schema.sql")
    add_bullet(pdf, "ensure_banks_exist() - inserts any missing bank rows")
    add_bullet(pdf, "get_rates() / get_dashboard_data() - read current rates")
    add_bullet(pdf, "clear_bank_rates(slug) - delete that bank's current rates before refresh")
    add_bullet(
        pdf,
        "upsert_rates_and_record_history(slug, points) - save new rates and write "
        "history when values change",
    )
    add_bullet(pdf, "export_to_excel() - builds Excel with openpyxl")
    add_bullet(pdf, "close_db() - called on app shutdown")

    # 8. rate_scrapers
    add_title(pdf, "8. rate_scrapers.py - Live bank scrapers")
    add_p(
        pdf,
        "This is the largest and most important file. Each bank has a scrape_*() "
        "function that downloads HTML/PDF/JSON from the official source and maps "
        "rates onto the CUB tenure rows.",
    )
    add_h2(pdf, "Shared helpers")
    add_bullet(pdf, "_fetch(url) - HTTP GET with browser-like headers")
    add_bullet(pdf, "_fetch_rendered(url) - Playwright for JS-heavy pages (if needed)")
    add_bullet(pdf, "parse_tenor_range(text) - convert '444 days' / '1 year to 3 years' into day min/max")
    add_bullet(pdf, "TenorBand - holds one bank tenor band and rates for slabs")
    add_bullet(
        pdf,
        "pick_rate(bands, day, slab) - choose the narrowest tenor band that covers "
        "a representative day (e.g. day 444 for the '444 days' row)",
    )
    add_bullet(
        pdf,
        "to_cub_format / to_cub_from_slab_tables - map bank bands into the standard "
        "dict shape: {callable: {tenure: {slab: rate}}, non_callable: ...}",
    )
    add_h2(pdf, "Per-bank methods")
    add_bullet(pdf, "HDFC - HTML interest-rates tables (<3 Cr and >=3 Cr, non-withdrawable)")
    add_bullet(pdf, "CUB - HTML deposit-interest-rate page (callable + non-callable, both slabs)")
    add_bullet(pdf, "Axis - PDF via pdfplumber (separate callable / FD Plus PDFs)")
    add_bullet(pdf, "IDFC - retail + bulk PDFs discovered from interest-rate page, HTML fallback")
    add_bullet(pdf, "IndusInd - rates.html tables, classified by premature-withdrawal headers")
    add_bullet(pdf, "ICICI - official JSON feed (fd-interest-rate.json)")
    add_bullet(pdf, "SBI - retail HTML tables (callable table 0, non-callable table 1)")
    add_bullet(
        pdf,
        "Yes Bank - CMS content API for callable <3 Cr; bulk PDF for 3-5 Cr callable "
        "and non-callable",
    )
    add_p(
        pdf,
        "SCRAPERS dict maps slug -> function. scrape_bank(slug) runs the matching scraper.",
    )

    # 9. scrapers
    add_title(pdf, "9. scrapers.py - RatePoint adapter")
    add_p(
        pdf,
        "LiveBankScraper.fetch_rates() calls rate_scrapers.scrape_bank(), then walks "
        "TENURE_ROWS and converts each published slab into a RatePoint. This is the "
        "object format db_storage expects.",
    )

    # 10. scrape_archive
    add_title(pdf, "10. scrape_archive.py - Local JSON history")
    add_p(
        pdf,
        "Every scrape creates data/scrapes/<timestamp>/. Each bank gets rates.json. "
        "summary.json lists success/fail and points_seen. Useful for debugging without "
        "querying MySQL.",
    )

    # 11. services
    add_title(pdf, "11. services.py - Business logic")
    add_h3(pdf, "scrape_banks()")
    add_p(
        pdf,
        "1) Ensure banks exist in MySQL. 2) Create archive session. 3) For each bank: "
        "clear old rates, fetch live rates, upsert + history, save JSON. 4) On failure, "
        "clear that bank's rates and store the error. 5) Write summary.json.",
    )
    add_h3(pdf, "build_bank_tables()")
    add_p(
        pdf,
        "Groups DB rates into CUB-style HTML tables. Missing slabs become '-'. Rows "
        "with both slabs empty are skipped. Empty whole tables are skipped.",
    )
    add_h3(pdf, "build_best_rate_comparison() / build_ranked_rates()")
    add_p(
        pdf,
        "Used by /compare. For each tenure, finds the highest rate per slab across "
        "banks, then builds full rankings.",
    )

    # 12. main
    add_title(pdf, "12. main.py - FastAPI routes")
    add_h2(pdf, "Lifecycle")
    add_bullet(pdf, "startup - optional init_db / scrape_banks (both off by default)")
    add_bullet(pdf, "shutdown - close MySQL connection")
    add_h2(pdf, "Pages")
    add_bullet(pdf, "GET / - dashboard (optional ?bank_slug=hdfc)")
    add_bullet(pdf, "GET /compare - best-rate comparison (?fd_type=callable|non_callable)")
    add_bullet(pdf, "POST /scrape/run-page - Refresh Rates button, then redirect to /")
    add_h2(pdf, "APIs / exports")
    add_bullet(pdf, "GET /banks, GET /rates, GET /rates/compare/best")
    add_bullet(pdf, "POST /scrape/run - JSON scrape for selected banks")
    add_bullet(pdf, "GET /export/csv, GET /export/excel")

    # 13. templates
    add_title(pdf, "13. templates/ - UI")
    add_bullet(pdf, "base.html - layout, CSS, nav (Home, Best Rates, Refresh, Export)")
    add_bullet(pdf, "index.html - bank chips + CUB rate tables + source links")
    add_bullet(pdf, "compare.html - best rate table + full ranking per tenure/slab")

    # 14. How one refresh works
    add_title(pdf, "14. End-to-end: clicking Refresh Rates")
    add_p(pdf, "Step by step:")
    add_bullet(pdf, "Browser POSTs /scrape/run-page")
    add_bullet(pdf, "services.scrape_banks() loops all scrapers")
    add_bullet(pdf, "Each scraper downloads official page/PDF/JSON and maps to CUB tenures")
    add_bullet(pdf, "scrapers.py turns mapped dict into list[RatePoint]")
    add_bullet(pdf, "db_storage clears old rows for that bank, inserts new rates, logs changes")
    add_bullet(pdf, "JSON archived under data/scrapes/<timestamp>/")
    add_bullet(pdf, "Redirect to /?scraped=1")
    add_bullet(pdf, "dashboard reads MySQL via get_dashboard_data() and renders tables")

    # 15. Run
    add_title(pdf, "15. How to run")
    add_code(
        pdf,
        "cd C:\\Users\\pratik.bhatkulkar\\Desktop\\FD\n"
        "python -m uvicorn main:app --host 127.0.0.1 --port 8000\n"
        "\n"
        "Open: http://127.0.0.1:8000",
    )
    add_p(
        pdf,
        "Ensure .env has MYSQL_* credentials. Keep INIT_DB_ON_STARTUP=false and "
        "SCRAPE_ON_STARTUP=false on Hostinger to avoid connection-limit errors. "
        "Starlette must stay compatible with FastAPI 0.115.5 "
        "(starlette>=0.40,<0.42).",
    )

    # 16. Why some cells are blank
    add_title(pdf, "16. Why some cells show '-'")
    add_p(
        pdf,
        "This is expected accuracy behavior, not a broken URL. Examples:",
    )
    add_bullet(pdf, "Yes Bank non-callable: bulk PDF has 3-5 Cr only (no <3 Cr)")
    add_bullet(pdf, "HDFC/Axis/IDFC non-callable <3 Cr at long tenors often not published")
    add_bullet(pdf, "SBI retail page has limited non-callable tenors and no 3-5 Cr slab")
    add_p(
        pdf,
        "If a bank publishes a rate you can see on their site but the app shows '-', "
        "that specific scraper/mapping needs a fix for that bank+tenure+slab.",
    )

    pdf.output(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
