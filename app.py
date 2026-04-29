import logging
import os
from flask import Flask, render_template, jsonify, request, abort
import db
import alerts
import scheduler
import fetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def _fmt(price):
    """Format price as $XXX,XXX."""
    return f"${price:,.0f}" if price else "—"


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    towns = db.get_towns()
    flat_types = db.get_flat_types()
    result = db.get_town_summary()
    if result:
        summary, latest_month = result
    else:
        summary, latest_month = [], "—"

    return render_template(
        "dashboard.html",
        towns=towns,
        flat_types=flat_types,
        summary=summary,
        latest_month=latest_month,
        fmt=_fmt,
    )


# ── JSON API (consumed by Chart.js on the frontend) ─────────────────────────

@app.route("/api/trend")
def api_trend():
    town = request.args.get("town", "")
    flat_type = request.args.get("flat_type", "4 ROOM")
    months = int(request.args.get("months", 24))
    if not town:
        abort(400, "town is required")
    data = db.get_price_trend(town, flat_type, months)
    return jsonify(data)


@app.route("/api/compare")
def api_compare():
    towns = request.args.getlist("town")
    flat_type = request.args.get("flat_type", "4 ROOM")
    months = int(request.args.get("months", 12))
    if not towns:
        abort(400, "at least one town required")
    data = db.compare_towns(towns, flat_type, months)
    return jsonify(data)


@app.route("/api/summary")
def api_summary():
    month = request.args.get("month")
    flat_type = request.args.get("flat_type")
    result = db.get_town_summary(month, flat_type)
    if not result:
        return jsonify({"rows": [], "month": "—"})
    rows, m = result
    return jsonify({"rows": rows, "month": m})


# ── Alert CRUD ───────────────────────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    return jsonify(db.get_active_alerts())


@app.route("/api/alerts", methods=["POST"])
def create_alert():
    body = request.get_json(force=True)
    town = body.get("town", "").strip().upper()
    flat_type = body.get("flat_type", "").strip().upper()
    direction = body.get("direction", "").strip().lower()
    threshold = body.get("threshold")

    if not all([town, flat_type, direction, threshold]):
        abort(400, "town, flat_type, direction, threshold are required")
    if direction not in ("above", "below"):
        abort(400, "direction must be 'above' or 'below'")

    db.add_alert(town, flat_type, direction, float(threshold))
    return jsonify({"status": "ok"}), 201


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
def delete_alert(alert_id: int):
    db.delete_alert(alert_id)
    return jsonify({"status": "ok"})


# ── Startup ──────────────────────────────────────────────────────────────────

def create_app():
    db.init_db()
    # Backfill missing months on startup (non-blocking in production)
    try:
        fetcher.backfill()
    except Exception as e:
        logger.warning("Backfill skipped: %s", e)
    scheduler.start()
    return app


if __name__ == "__main__":
    create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
