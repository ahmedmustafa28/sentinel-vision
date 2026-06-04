import threading
import time
from datetime import datetime, timezone
import logging

from app.core.config import get_settings

logger = logging.getLogger("AlertThrottle")


class AlertThrottle:
    """Manages alert rate-limiting, deduplication, and periodic digests for critical notifications."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._initialized = True
            self.settings = get_settings()
            self.cooldowns: dict[tuple[int, str], float] = {}  # (camera_id, event_type) -> timestamp (float)
            self.digest_batches: dict[tuple[int, str], dict] = {}  # (camera_id, event_type) -> aggregated details
            
            self._stop_event = threading.Event()
            self.digest_thread: threading.Thread | None = None
            
            # Start digest thread if digest mode is enabled in the configuration
            if self.settings.alert_digest_minutes and self.settings.alert_digest_minutes > 0:
                self.digest_thread = threading.Thread(
                    target=self._digest_loop,
                    name="alert-digest-loop",
                    daemon=True
                )
                self.digest_thread.start()
                logger.info("AlertThrottle digest thread started with window %s minutes", self.settings.alert_digest_minutes)

    def should_fire(
        self,
        *,
        camera_id: int,
        camera_name: str,
        event_type: str,
        notification_id: int,
        event_time: datetime,
        description: str = "",
    ) -> bool:
        """
        Evaluates whether an alert for a given camera and event type is allowed to fire.
        Returns True if the alert is allowed (cooldown elapsed/inactive), or False if throttled.
        If digest mode is active, throttled alerts are batched for future dispatch.
        """
        current_time = time.time()
        cooldown_seconds = self.settings.alert_cooldown_seconds

        with self._lock:
            key = (camera_id, event_type)
            last_fired = self.cooldowns.get(key)
            
            if last_fired is None or (current_time - last_fired) >= cooldown_seconds:
                # Update cooldown timestamp and allow alert to fire
                self.cooldowns[key] = current_time
                return True

            # Alert is suppressed! Batch it if digest mode is enabled.
            if self.settings.alert_digest_minutes and self.settings.alert_digest_minutes > 0:
                if key not in self.digest_batches:
                    self.digest_batches[key] = {
                        "camera_id": camera_id,
                        "camera_name": camera_name,
                        "event_type": event_type,
                        "count": 1,
                        "first_occurrence": event_time,
                        "last_occurrence": event_time,
                        "notification_ids": [notification_id],
                    }
                else:
                    batch_item = self.digest_batches[key]
                    batch_item["count"] += 1
                    batch_item["last_occurrence"] = event_time
                    batch_item["notification_ids"].append(notification_id)
                    if event_time < batch_item["first_occurrence"]:
                        batch_item["first_occurrence"] = event_time

            return False

    def send_digest(self) -> None:
        """Aggregates batched alerts, dispatches a summary email, and updates DB statuses."""
        with self._lock:
            batch = self.digest_batches.copy()
            self.digest_batches.clear()

        if not batch:
            return

        subject = "[DIGEST ALERT] Suppressed Surveillance Events Summary"
        body_parts = [
            "AI CCTV Surveillance - Alert Digest Summary\n",
            "The following events were suppressed during the last digest window due to active cooldowns:\n",
            "=" * 60
        ]

        all_notif_ids = []
        for key, item in batch.items():
            first_str = item["first_occurrence"].isoformat() if hasattr(item["first_occurrence"], "isoformat") else str(item["first_occurrence"])
            last_str = item["last_occurrence"].isoformat() if hasattr(item["last_occurrence"], "isoformat") else str(item["last_occurrence"])

            body_parts.append(
                f"Camera: {item['camera_name']} (ID: {item['camera_id']})\n"
                f"Event Type: {item['event_type']}\n"
                f"Suppressed Count: {item['count']}\n"
                f"First Occurrence: {first_str}\n"
                f"Last Occurrence: {last_str}\n"
                f"{'-' * 45}"
            )
            all_notif_ids.extend(item["notification_ids"])

        body_parts.append("\nThis is an automated digest message from your AI CCTV Surveillance system.")
        email_body = "\n".join(body_parts)

        # Send the alert email via NotificationService
        from app.services.notification_service import NotificationService
        notifier = NotificationService()
        logger.info("Dispatching alert digest email containing %s suppressed alerts", len(all_notif_ids))
        success = notifier._send_email_alert(subject=subject, body=email_body)

        # Update the notification rows in the database
        from app.db.session import SessionLocal, commit_with_retry
        from app.db.crud_notification import get_notification_by_id

        db = SessionLocal()
        try:
            for notif_id in all_notif_ids:
                notif = get_notification_by_id(db, notif_id)
                if notif:
                    if success:
                        notif.email_sent = True
                        notif.status = "SENT"
                    else:
                        notif.status = "FAILED"
            commit_with_retry(db)
            logger.info("Successfully updated notification statuses in database for the digest batch")
        except Exception as exc:
            logger.error("Failed to update database for digest notifications: %s", exc)
            db.rollback()
        finally:
            db.close()

    def _digest_loop(self) -> None:
        logger.info("AlertThrottle digest loop thread running")
        last_run = time.time()
        while not self._stop_event.is_set():
            now = time.time()
            interval = (self.settings.alert_digest_minutes or 5) * 60
            if now - last_run >= interval:
                try:
                    self.send_digest()
                except Exception as exc:
                    logger.error("Error in send_digest: %s", exc)
                last_run = now
            # Sleep in small periods to react quickly to shutdown
            time.sleep(1)

    def stop(self) -> None:
        """Stops the background digest loop thread and clears the instance."""
        if self.digest_thread and self.digest_thread.is_alive():
            logger.info("Stopping AlertThrottle digest loop thread")
            self._stop_event.set()
            self.digest_thread.join(timeout=3)
        with self._lock:
            self._initialized = False
            AlertThrottle._instance = None
