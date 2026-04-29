import requests
import logging
import time
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import db
from config import API_BASE, RESOURCE_ID, PAGE_SIZE, BACKFILL_MONTHS

logger = logging.getLogger(__name__)

# Polite delay between pages to avoid 429s
REQUEST_DELAY = 0.5   # seconds between pages
RETRY_DELAY   = 5.0   # seconds to wait after a 429


def _get_with_retry(params: dict, retries: int = 3) -> dict:
    """GET with exponential backoff on 429."""
    for attempt in range(retries):
        resp = requests.get(API_BASE, params=params, timeout=30)
        if resp.status_code == 429:
            wait = RETRY_DELAY * (2 ** attempt)
            logger.warning("Rate limited — waiting %.0fs (attempt %d/%d)", wait, attempt + 1, retries)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Failed after {retries} retries (429)")


def _month_range(start: str, end: str) -> list[str]:
    """Return list of 'YYYY-MM' strings from start to end inclusive."""
    cur = datetime.strptime(start, "%Y-%m")
    stop = datetime.strptime(end, "%Y-%m")
    months = []
    while cur <= stop:
        months.append(cur.strftime("%Y-%m"))
        cur += relativedelta(months=1)
    return months


def _fetch_month(month: str) -> list[dict]:
    """Fetch all transactions for a given month, handling pagination."""
    records = []
    offset = 0
    while True:
        params = {
            "resource_id": RESOURCE_ID,
            "limit": PAGE_SIZE,
            "offset": offset,
            "filters": f'{{"month":"{month}"}}',
        }
        data = _get_with_retry(params)
        time.sleep(REQUEST_DELAY)

        if not data.get("success"):
            logger.warning("API returned success=false for month %s", month)
            break

        batch = data["result"]["records"]
        if not batch:
            break

        for r in batch:
            records.append({
                "month":          r.get("month", ""),
                "town":           r.get("town", ""),
                "flat_type":      r.get("flat_type", ""),
                "block":          r.get("block", ""),
                "street_name":    r.get("street_name", ""),
                "storey_range":   r.get("storey_range", ""),
                "floor_area_sqm": float(r["floor_area_sqm"]) if r.get("floor_area_sqm") else None,
                "flat_model":     r.get("flat_model", ""),
                "lease_commence": int(r["lease_commence_date"]) if r.get("lease_commence_date") else None,
                "remaining_lease": r.get("remaining_lease", ""),
                "resale_price":   float(r["resale_price"]) if r.get("resale_price") else None,
            })

        offset += PAGE_SIZE
        if offset >= data["result"]["total"]:
            break

    return records


def fetch_and_store(month: str) -> int:
    """Fetch one month, insert into DB, rebuild snapshot. Returns record count."""
    logger.info("Fetching %s ...", month)
    records = _fetch_month(month)
    if not records:
        logger.info("No records for %s", month)
        return 0

    inserted = db.insert_transactions(records)
    db.rebuild_snapshots(month)

    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO fetch_log (month, records_inserted) VALUES (?, ?)",
            (month, inserted)
        )

    logger.info("Stored %d records for %s", inserted, month)
    return inserted


def backfill():
    """
    On first run: fetch the last BACKFILL_MONTHS months.
    On subsequent runs: fetch any months between latest stored and today.
    """
    today = date.today()
    current_month = today.strftime("%Y-%m")

    latest = db.get_latest_fetched_month()

    if latest is None:
        # First run — backfill
        start_dt = datetime.strptime(current_month, "%Y-%m") - relativedelta(months=BACKFILL_MONTHS - 1)
        start = start_dt.strftime("%Y-%m")
        logger.info("First run — backfilling from %s to %s", start, current_month)
    else:
        # Resume from the month after the latest stored
        start_dt = datetime.strptime(latest, "%Y-%m") + relativedelta(months=1)
        start = start_dt.strftime("%Y-%m")
        if start > current_month:
            logger.info("Already up to date (latest: %s)", latest)
            return
        logger.info("Incremental fetch from %s to %s", start, current_month)

    months = _month_range(start, current_month)
    total = 0
    for month in months:
        try:
            total += fetch_and_store(month)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", month, e)

    logger.info("Backfill complete — %d total records stored", total)


def daily_fetch():
    """Called by APScheduler each day — fetches current month."""
    today = date.today()
    current_month = today.strftime("%Y-%m")
    logger.info("Daily fetch triggered for %s", current_month)
    fetch_and_store(current_month)
