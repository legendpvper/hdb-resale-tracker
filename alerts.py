import logging
import db
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured — skipping alert push")
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram alert sent")
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


def check_and_fire():
    """Compare latest avg prices against all active alerts. Fire if triggered."""
    alerts = db.get_active_alerts()
    if not alerts:
        return

    # Get latest month
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(month) as m FROM monthly_snapshots"
        ).fetchone()
        latest_month = row["m"] if row else None

    if not latest_month:
        return

    for alert in alerts:
        latest = db.get_latest_avg(alert["town"], alert["flat_type"])
        if not latest:
            continue

        avg = latest["avg_price"]
        threshold = alert["threshold"]
        direction = alert["direction"]

        triggered = (
            (direction == "above" and avg > threshold) or
            (direction == "below" and avg < threshold)
        )

        if triggered:
            direction_word = "risen above" if direction == "above" else "fallen below"
            msg = (
                f"🏠 *HDB Resale Alert*\n\n"
                f"*{alert['town']}* — {alert['flat_type']}\n"
                f"Avg price has {direction_word} your threshold of "
                f"*${threshold:,.0f}*\n\n"
                f"Current avg: *${avg:,.0f}* ({latest_month})"
            )
            _send_telegram(msg)
            db.log_alert_fired(alert["id"], latest_month, avg)
            logger.info(
                "Alert fired: %s %s %s $%.0f (threshold $%.0f)",
                alert["town"], alert["flat_type"], direction, avg, threshold
            )
