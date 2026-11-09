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

## Deploy on Render

The `render.yaml` Blueprint creates the web service and PostgreSQL database. Push this file to the `postgres-migration` branch, then create a Blueprint in the Render Dashboard from that branch and apply it. The schema is initialized automatically on startup; click **Refresh Rates** after deployment to populate current rates.

The Blueprint uses free plans for an initial trial. Render's free PostgreSQL databases expire after 30 days and are deleted after the grace period unless upgraded. Scrape archive files are stored on the web service's ephemeral filesystem and can be lost on restart or deploy. Upgrade the database and use persistent storage or external object storage before relying on this deployment for durable data.

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
