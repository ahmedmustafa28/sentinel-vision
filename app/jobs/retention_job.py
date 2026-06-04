import os
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings, BASE_DIR

logger = logging.getLogger("RetentionJob")

# In-memory history tracking
last_run_time: datetime | None = None
scheduler: BackgroundScheduler | None = None


def run_retention_cleanup(retention_days: int, snapshot_dir: Path) -> dict:
    """
    Deletes snapshot image files and database event records older than retention_days.
    Updates the last_run_time timestamp when executed.
    """
    global last_run_time
    last_run_time = datetime.now(timezone.utc)
    
    logger.info("Starting retention cleanup job. Max retention: %s days", retention_days)

    # 1. Cleanup snapshot files
    deleted_snapshots = 0
    now = time.time()
    cutoff_epoch = now - (retention_days * 86400)

    if snapshot_dir.exists() and snapshot_dir.is_dir():
        for filename in os.listdir(snapshot_dir):
            file_path = snapshot_dir / filename
            if file_path.is_file():
                try:
                    mtime = file_path.stat().st_mtime
                    if mtime < cutoff_epoch:
                        os.remove(file_path)
                        deleted_snapshots += 1
                except Exception as exc:
                    logger.error("Failed to delete snapshot file %s: %s", file_path, exc)

    # 2. Cleanup DB Event records
    deleted_db_records = 0
    cutoff_db = datetime.now(timezone.utc) - timedelta(days=retention_days)

    from app.db.session import SessionLocal, commit_with_retry
    from app.models.event import Event

    db = SessionLocal()
    try:
        # Delete Event records older than threshold
        deleted_db_records = db.query(Event).filter(Event.timestamp < cutoff_db).delete(synchronize_session=False)
        commit_with_retry(db)
        logger.info("Retention cleanup: deleted %s snapshots, %s event records", deleted_snapshots, deleted_db_records)
    except Exception as exc:
        logger.error("Failed to execute DB retention cleanup: %s", exc)
        db.rollback()
    finally:
        db.close()

    return {
        "deleted_snapshots": deleted_snapshots,
        "deleted_event_records": deleted_db_records
    }


def scheduler_job_wrapper() -> None:
    """Wrapper function to be invoked by APScheduler."""
    settings = get_settings()
    snapshot_dir = (BASE_DIR / settings.event_snapshot_dir).resolve()
    run_retention_cleanup(settings.event_retention_days, snapshot_dir)


def start_scheduler() -> BackgroundScheduler:
    """Starts the background scheduler and registers the daily retention cleanup cron job."""
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        
        # Register daily at 02:00 local time
        scheduler.add_job(
            func=scheduler_job_wrapper,
            trigger=CronTrigger(hour=2, minute=0),
            id="retention_cleanup",
            name="Daily retention cleanup job",
            replace_existing=True
        )
        scheduler.start()
        logger.info("APScheduler initialized and daily retention cleanup job registered.")
    return scheduler


def stop_scheduler() -> None:
    """Cleanly shuts down the background scheduler."""
    global scheduler
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down successfully.")
        except Exception as exc:
            logger.error("Failed to shut down APScheduler: %s", exc)
        finally:
            scheduler = None
