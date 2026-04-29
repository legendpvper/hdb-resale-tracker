import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                month           TEXT NOT NULL,
                town            TEXT NOT NULL,
                flat_type       TEXT NOT NULL,
                block           TEXT,
                street_name     TEXT,
                storey_range    TEXT,
                floor_area_sqm  REAL,
                flat_model      TEXT,
                lease_commence  INTEGER,
                remaining_lease TEXT,
                resale_price    REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_month_town
                ON transactions(month, town);

            CREATE INDEX IF NOT EXISTS idx_town_flat
                ON transactions(town, flat_type);

            CREATE TABLE IF NOT EXISTS monthly_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                month       TEXT NOT NULL,
                town        TEXT NOT NULL,
                flat_type   TEXT NOT NULL,
                avg_price   REAL,
                median_price REAL,
                min_price   REAL,
                max_price   REAL,
                tx_count    INTEGER,
                UNIQUE(month, town, flat_type)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                town        TEXT NOT NULL,
                flat_type   TEXT NOT NULL,
                direction   TEXT NOT NULL CHECK(direction IN ('above', 'below')),
                threshold   REAL NOT NULL,
                active      INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(town, flat_type, direction, threshold)
            );

            CREATE TABLE IF NOT EXISTS alert_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id    INTEGER REFERENCES alerts(id),
                month       TEXT,
                avg_price   REAL,
                fired_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS fetch_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                month       TEXT NOT NULL,
                records_inserted INTEGER,
                fetched_at  TEXT DEFAULT (datetime('now'))
            );
        """)
    logger.info("Database initialised at %s", DB_PATH)


def get_latest_fetched_month():
    """Return the most recent month already in transactions, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(month) as m FROM transactions"
        ).fetchone()
        return row["m"] if row else None


def insert_transactions(records: list[dict]):
    """Bulk-insert raw API records, ignore duplicates."""
    sql = """
        INSERT OR IGNORE INTO transactions
            (month, town, flat_type, block, street_name, storey_range,
             floor_area_sqm, flat_model, lease_commence, remaining_lease,
             resale_price)
        VALUES
            (:month, :town, :flat_type, :block, :street_name, :storey_range,
             :floor_area_sqm, :flat_model, :lease_commence, :remaining_lease,
             :resale_price)
    """
    with get_conn() as conn:
        conn.executemany(sql, records)
    return len(records)


def rebuild_snapshots(month: str):
    """Recompute monthly_snapshots for a given month from raw transactions."""
    sql = """
        INSERT OR REPLACE INTO monthly_snapshots
            (month, town, flat_type, avg_price, median_price,
             min_price, max_price, tx_count)
        SELECT
            month,
            town,
            flat_type,
            ROUND(AVG(resale_price), 0),
            NULL,               -- SQLite has no MEDIAN; computed in Python
            MIN(resale_price),
            MAX(resale_price),
            COUNT(*)
        FROM transactions
        WHERE month = ?
        GROUP BY month, town, flat_type
    """
    with get_conn() as conn:
        conn.execute(sql, (month,))


# ── Query helpers used by Flask routes ──────────────────────────────────────

def get_towns():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT town FROM transactions ORDER BY town"
        ).fetchall()
        return [r["town"] for r in rows]


def get_flat_types():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT flat_type FROM transactions ORDER BY flat_type"
        ).fetchall()
        return [r["flat_type"] for r in rows]


def get_price_trend(town: str, flat_type: str, months: int = 24):
    """Return monthly avg price for a town+flat_type over the last N months."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT month, avg_price, tx_count
            FROM monthly_snapshots
            WHERE town = ? AND flat_type = ?
            ORDER BY month DESC
            LIMIT ?
        """, (town, flat_type, months)).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_latest_avg(town: str, flat_type: str):
    """Return the most recent avg price for a town+flat_type."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT avg_price, month
            FROM monthly_snapshots
            WHERE town = ? AND flat_type = ?
            ORDER BY month DESC
            LIMIT 1
        """, (town, flat_type)).fetchone()
        return dict(row) if row else None


def get_town_summary(month: str = None, flat_type: str = None):
    """Return avg price per town for a given month, optionally filtered by flat_type."""
    with get_conn() as conn:
        if not month:
            row = conn.execute(
                "SELECT MAX(month) as m FROM monthly_snapshots"
            ).fetchone()
            month = row["m"] if row else None
        if not month:
            return []

        if flat_type:
            rows = conn.execute("""
                SELECT town,
                       ROUND(AVG(avg_price), 0) as avg_price,
                       SUM(tx_count) as tx_count
                FROM monthly_snapshots
                WHERE month = ? AND flat_type = ?
                GROUP BY town
                ORDER BY avg_price DESC
            """, (month, flat_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT town,
                       ROUND(AVG(avg_price), 0) as avg_price,
                       SUM(tx_count) as tx_count
                FROM monthly_snapshots
                WHERE month = ?
                GROUP BY town
                ORDER BY avg_price DESC
            """, (month,)).fetchall()
        return [dict(r) for r in rows], month


def compare_towns(towns: list, flat_type: str, months: int = 12):
    """Return monthly avg price for multiple towns — for comparison chart."""
    placeholders = ",".join("?" * len(towns))
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT month, town, avg_price
            FROM monthly_snapshots
            WHERE town IN ({placeholders})
              AND flat_type = ?
            ORDER BY month ASC
        """, (*towns, flat_type)).fetchall()
        return [dict(r) for r in rows]


def get_active_alerts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE active = 1"
        ).fetchall()
        return [dict(r) for r in rows]


def add_alert(town: str, flat_type: str, direction: str, threshold: float):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO alerts (town, flat_type, direction, threshold)
            VALUES (?, ?, ?, ?)
        """, (town, flat_type, direction, threshold))


def delete_alert(alert_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE alerts SET active = 0 WHERE id = ?", (alert_id,))


def log_alert_fired(alert_id: int, month: str, avg_price: float):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO alert_history (alert_id, month, avg_price)
            VALUES (?, ?, ?)
        """, (alert_id, month, avg_price))
