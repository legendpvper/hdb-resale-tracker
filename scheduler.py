import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import fetcher
import alerts

logger = logging.getLogger(__name__)

_scheduler = None


def start():
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Singapore")

    # Daily at 8am SGT — fetch current month data
    _scheduler.add_job(
        fetcher.daily_fetch,
        CronTrigger(hour=8, minute=0, timezone="Asia/Singapore"),
        id="daily_fetch",
        replace_existing=True,
    )

    # Daily at 8:05am SGT — check alerts after fetch
    _scheduler.add_job(
        alerts.check_and_fire,
        CronTrigger(hour=8, minute=5, timezone="Asia/Singapore"),
        id="alert_check",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started — daily fetch at 08:00 SGT, alert check at 08:05 SGT")


def stop():
    if _scheduler:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")
