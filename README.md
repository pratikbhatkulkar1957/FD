# FD Rates (PostgreSQL)

FastAPI app to scrape and compare Fixed Deposit rates across Indian banks.

Data is stored in PostgreSQL. Each scrape also saves JSON files under `data/scrapes/<timestamp>/`.

## Run

```powershell
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open: http://localhost:8000/

## Setup

1. Set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DATABASE` in `.env`.
2. Run `schema.sql` against your PostgreSQL database (creates `banks`, `fd_rates`, `rate_history`).
3. Start the server and click **Refresh Rates**.

## Scrape folders

Each scrape creates:

```
data/scrapes/2026-07-11_12-45-30/
  summary.json
  hdfc/rates.json
  icici/rates.json
  ...
```

## Project files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app and routes |
| `db_storage.py` | PostgreSQL read/write |
| `services.py` | Scrape orchestration and tables |
| `rate_scrapers.py` | Bank website scrapers |
| `scrape_archive.py` | Timestamped scrape folder storage |
| `schema.sql` | PostgreSQL table definitions |
