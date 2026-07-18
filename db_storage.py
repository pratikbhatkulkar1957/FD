"""
MySQL storage layer for banks, current FD rates, and rate history.

Important: uses ONE shared connection (_conn) re-used across requests.
Hostinger shared MySQL limits connections-per-hour, so we must not
open a new connection for every query.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pymysql
from openpyxl import Workbook
from pymysql.cursors import DictCursor

from bank_data import BANKS
from config import settings

logger = logging.getLogger(__name__)

# Thread-safe single-connection pool (size = 1) for Hostinger limits.
_lock = threading.Lock()
_conn: pymysql.Connection | None = None
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


@dataclass
class BankRow:
    """One row from the banks table."""

    slug: str
    name: str


@dataclass
class RateRow:
    """One current rate cell from fd_rates."""

    bank_slug: str
    fd_type: str
    tenure_label: str
    tenure_min_days: int
    tenure_max_days: int
    deposit_slab: str
    sort_order: int
    rate_percent: Decimal
    source_url: str | None
    updated_at: datetime | None


@dataclass
class HistoryRow:
    """One historical change from rate_history."""

    bank_slug: str
    fd_type: str
    tenure_label: str
    deposit_slab: str
    rate_percent: Decimal
    source_url: str | None
    changed_at: datetime | None


@dataclass
class DashboardData:
    """Bundle returned by get_dashboard_data() for the home page."""

    rates: list[RateRow]
    history_count: int
    last_updated: datetime | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _validate_mysql_settings() -> None:
    missing = [
        name
        for name, value in [
            ("MYSQL_HOST", settings.MYSQL_HOST),
            ("MYSQL_USER", settings.MYSQL_USER),
            ("MYSQL_PASSWORD", settings.MYSQL_PASSWORD),
            ("MYSQL_DATABASE", settings.MYSQL_DATABASE),
        ]
        if not value
    ]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing MySQL settings in .env: {names}")


def _new_connection() -> pymysql.Connection:
    _validate_mysql_settings()
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=20,
        read_timeout=60,
        write_timeout=60,
    )


def _reset_connection() -> None:
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def _get_connection() -> pymysql.Connection:
    """Reuse one MySQL connection per process to stay under Hostinger limits."""
    global _conn
    if _conn is None:
        _conn = _new_connection()
        return _conn
    try:
        _conn.ping(reconnect=True)
    except Exception:
        _reset_connection()
        _conn = _new_connection()
    return _conn


@contextmanager
def _db():
    """Serialize DB access and reuse a single shared connection."""
    with _lock:
        conn = _get_connection()
        try:
            yield conn
        except pymysql.err.OperationalError:
            _reset_connection()
            raise
        except Exception:
            conn.rollback()
            raise


def close_db() -> None:
    """Close the shared connection (app shutdown)."""
    with _lock:
        _reset_connection()


def init_db() -> None:
    """Apply the MySQL schema to the configured Hostinger database."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [s.strip() for s in schema_sql.split(";") if s.strip()]

    with _db() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()


def get_banks() -> list[BankRow]:
    """Load all banks currently stored in MySQL."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug, name FROM banks ORDER BY name")
            rows = cur.fetchall()
        return [BankRow(slug=r["slug"], name=r["name"]) for r in rows]


def ensure_banks_exist(bank_slugs: list[str]) -> None:
    """Insert/update bank rows so foreign keys on fd_rates succeed."""
    with _db() as conn:
        with conn.cursor() as cur:
            for slug in bank_slugs:
                meta = BANKS.get(slug, {})
                name = meta.get("name", slug.upper())
                cur.execute(
                    """
                    INSERT INTO banks (slug, name)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (slug, name),
                )
        conn.commit()


def _rows_to_rate_rows(rows: list[dict]) -> list[RateRow]:
    return [
        RateRow(
            bank_slug=r["bank_slug"],
            fd_type=r["fd_type"],
            tenure_label=r["tenure_label"],
            tenure_min_days=int(r["tenure_min_days"]),
            tenure_max_days=int(r["tenure_max_days"]),
            deposit_slab=r["deposit_slab"],
            sort_order=int(r["sort_order"] or 0),
            rate_percent=Decimal(str(r["rate_percent"])).quantize(Decimal("0.01")),
            source_url=r["source_url"],
            updated_at=_parse_datetime(r["updated_at"]),
        )
        for r in rows
    ]


def get_rates() -> list[RateRow]:
    """Return all current FD rate rows ordered for display."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bank_slug, fd_type, tenure_label, tenure_min_days,
                       tenure_max_days, deposit_slab, sort_order,
                       rate_percent, source_url, updated_at
                FROM fd_rates
                ORDER BY bank_slug, fd_type, sort_order, deposit_slab
                """
            )
            rows = cur.fetchall()
        return _rows_to_rate_rows(rows)


def get_all_history() -> list[HistoryRow]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bank_slug, fd_type, tenure_label, deposit_slab,
                       rate_percent, source_url, changed_at
                FROM rate_history
                ORDER BY changed_at DESC
                """
            )
            rows = cur.fetchall()

        return [
            HistoryRow(
                bank_slug=r["bank_slug"],
                fd_type=r["fd_type"],
                tenure_label=r["tenure_label"],
                deposit_slab=r["deposit_slab"],
                rate_percent=Decimal(str(r["rate_percent"])).quantize(Decimal("0.01")),
                source_url=r["source_url"],
                changed_at=_parse_datetime(r["changed_at"]),
            )
            for r in rows
        ]


def get_dashboard_data() -> DashboardData:
    """Fetch rates, history count, and last-updated in one DB round-trip."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bank_slug, fd_type, tenure_label, tenure_min_days,
                       tenure_max_days, deposit_slab, sort_order,
                       rate_percent, source_url, updated_at
                FROM fd_rates
                ORDER BY bank_slug, fd_type, sort_order, deposit_slab
                """
            )
            rate_rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS history_count FROM rate_history")
            history_count = int(cur.fetchone()["history_count"])
            cur.execute("SELECT MAX(updated_at) AS last_updated FROM fd_rates")
            last_updated = _parse_datetime(cur.fetchone()["last_updated"])

    return DashboardData(
        rates=_rows_to_rate_rows(rate_rows),
        history_count=history_count,
        last_updated=last_updated,
    )


def clear_bank_rates(bank_slug: str) -> None:
    """Delete current rates for one bank (called before a fresh scrape)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fd_rates WHERE bank_slug = %s", (bank_slug,))
        conn.commit()


def upsert_rates_and_record_history(
    bank_slug: str,
    points: list,
    *,
    diff_tolerance: Decimal = Decimal("0.00"),
) -> int:
    """
    Insert/update each RatePoint into fd_rates.
    When the rate value changes, also append a row to rate_history.
    Returns how many points newly changed.
    """
    changed = 0
    now = _now()

    with _db() as conn:
        with conn.cursor() as cur:
            for p in points:
                key = (bank_slug, p.fd_type, p.tenure_label, p.deposit_slab)
                new_rate = Decimal(p.rate_percent).quantize(Decimal("0.01"))

                cur.execute(
                    """
                    SELECT id, rate_percent, source_url
                    FROM fd_rates
                    WHERE bank_slug = %s AND fd_type = %s AND tenure_label = %s
                      AND deposit_slab = %s
                    """,
                    key,
                )
                row = cur.fetchone()

                if row is None:
                    cur.execute(
                        """
                        INSERT INTO fd_rates (
                            bank_slug, fd_type, tenure_label, tenure_min_days,
                            tenure_max_days, deposit_slab, sort_order,
                            rate_percent, source_url, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            bank_slug,
                            p.fd_type,
                            p.tenure_label,
                            p.tenure_min_days,
                            p.tenure_max_days,
                            p.deposit_slab,
                            p.sort_order,
                            new_rate,
                            p.source_url,
                            now,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO rate_history (
                            bank_slug, fd_type, tenure_label, deposit_slab,
                            rate_percent, source_url, changed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            bank_slug,
                            p.fd_type,
                            p.tenure_label,
                            p.deposit_slab,
                            new_rate,
                            p.source_url,
                            now,
                        ),
                    )
                    changed += 1
                    continue

                old_rate = Decimal(str(row["rate_percent"])).quantize(Decimal("0.01"))
                rate_changed = abs(old_rate - new_rate) > diff_tolerance
                url_changed = (row["source_url"] or "") != (p.source_url or "")

                if not rate_changed and not url_changed:
                    continue

                if rate_changed:
                    cur.execute(
                        """
                        UPDATE fd_rates
                        SET rate_percent = %s, source_url = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (new_rate, p.source_url, now, row["id"]),
                    )
                    cur.execute(
                        """
                        INSERT INTO rate_history (
                            bank_slug, fd_type, tenure_label, deposit_slab,
                            rate_percent, source_url, changed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            bank_slug,
                            p.fd_type,
                            p.tenure_label,
                            p.deposit_slab,
                            new_rate,
                            p.source_url,
                            now,
                        ),
                    )
                    changed += 1
                else:
                    cur.execute(
                        """
                        UPDATE fd_rates
                        SET source_url = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (p.source_url, now, row["id"]),
                    )

        conn.commit()

    return changed


def get_last_updated() -> datetime | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(updated_at) AS last_updated FROM fd_rates")
            row = cur.fetchone()
        return _parse_datetime(row["last_updated"]) if row else None


def export_to_excel(output_path: Path | None = None) -> Path:
    """Export current MySQL data to an Excel workbook for download."""
    path = output_path or Path(settings.EXCEL_EXPORT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug, name FROM banks ORDER BY name")
            banks = cur.fetchall()
            cur.execute(
                """
                SELECT bank_slug, fd_type, tenure_label, tenure_min_days,
                       tenure_max_days, deposit_slab, sort_order,
                       rate_percent, source_url, updated_at
                FROM fd_rates
                ORDER BY bank_slug, fd_type, sort_order, deposit_slab
                """
            )
            rates = cur.fetchall()
            cur.execute(
                """
                SELECT bank_slug, fd_type, tenure_label, deposit_slab,
                       rate_percent, source_url, changed_at
                FROM rate_history
                ORDER BY changed_at DESC
                """
            )
            history = cur.fetchall()

    wb = Workbook()
    banks_ws = wb.active
    banks_ws.title = "banks"
    banks_ws.append(["slug", "name"])
    for b in banks:
        banks_ws.append([b["slug"], b["name"]])

    rates_ws = wb.create_sheet("fd_rates")
    rates_ws.append([
        "bank_slug", "fd_type", "tenure_label", "tenure_min_days", "tenure_max_days",
        "deposit_slab", "sort_order", "rate_percent", "source_url", "updated_at",
    ])
    for r in rates:
        updated_at = _parse_datetime(r["updated_at"])
        rates_ws.append([
            r["bank_slug"],
            r["fd_type"],
            r["tenure_label"],
            r["tenure_min_days"],
            r["tenure_max_days"],
            r["deposit_slab"],
            r["sort_order"],
            float(r["rate_percent"]),
            r["source_url"] or "",
            updated_at.isoformat() if updated_at else "",
        ])

    history_ws = wb.create_sheet("rate_history")
    history_ws.append([
        "bank_slug", "fd_type", "tenure_label", "deposit_slab",
        "rate_percent", "source_url", "changed_at",
    ])
    for h in history:
        changed_at = _parse_datetime(h["changed_at"])
        history_ws.append([
            h["bank_slug"],
            h["fd_type"],
            h["tenure_label"],
            h["deposit_slab"],
            float(h["rate_percent"]),
            h["source_url"] or "",
            changed_at.isoformat() if changed_at else "",
        ])

    wb.save(path)
    return path
