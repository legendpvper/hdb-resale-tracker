# HDB Resale Tracker

A Flask dashboard for tracking HDB resale flat price trends across all Singapore towns. Pulls live data daily from [data.gov.sg](https://data.gov.sg), stores it in SQLite, and sends Telegram alerts when average prices cross user-defined thresholds.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-black?style=flat&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)

---

## Features

- **Market overview** — avg resale price ranked by town, filterable by flat type (2-room to Executive)
- **Price trend chart** — monthly avg price over 12 or 24 months for any town + flat type combination
- **Town comparison** — overlay up to 5 towns on a single chart to compare trajectories
- **Price alerts** — set above/below thresholds per town and flat type; fires a Telegram notification when crossed
- **Auto backfill** — on first run, fetches the last 24 months of transactions automatically
- **Daily scheduler** — APScheduler fetches the current month's data every morning at 08:00 SGT

## Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Scheduling | APScheduler |
| Database | SQLite |
| Data source | data.gov.sg Datastore API |
| Notifications | Telegram Bot API |
| Frontend | Chart.js, vanilla JS |
| Deployment | Render (free tier) |

## Project Structure

```
hdb-tracker/
├── app.py           # Flask app + all routes
├── fetcher.py       # data.gov.sg API calls + pagination + backfill
├── db.py            # SQLite schema + query helpers
├── alerts.py        # Threshold comparator + Telegram push
├── scheduler.py     # APScheduler daily jobs (fetch + alert check)
├── config.py        # Env vars, constants, town/flat type lists
├── templates/
│   └── dashboard.html
├── .env.example
├── render.yaml
└── requirements.txt
```

## Getting Started

### 1. Clone and install

```bash
git clone https://github.com/legendpvper/hdb-resale-tracker.git
cd hdb-resale-tracker
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DB_PATH=hdb_tracker.db
```

Telegram is optional — the app runs fine without it, alerts just won't push.

### 3. Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000). On first boot, the app automatically backfills the last 24 months of HDB resale data (~10 minutes due to data.gov.sg rate limits).

## Deployment on Render

The repo includes a `render.yaml` for one-click deployment.

1. Push to GitHub
2. Create a new **Web Service** on [Render](https://render.com) and connect the repo
3. Add environment variables: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`
4. Deploy — Render picks up `render.yaml` automatically

> **Note:** Render's free tier has ephemeral storage, so the SQLite database resets on each redeploy. The backfill on startup repopulates it automatically.

## Data Source

Transaction data is sourced from the [HDB Resale Flat Prices dataset](https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view) on data.gov.sg, updated monthly. The API is free and does not require authentication for basic usage (rate limited to ~10 req/min).

## License

MIT
