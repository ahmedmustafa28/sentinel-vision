from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Any

from app.db.session import get_db_session
from app.db.crud_notification import (
    get_unread_notification_count,
    list_notifications,
    mark_notification_as_read,
)

router = APIRouter()


@router.get(
    "/api/notifications/unread",
    summary="Get unread notifications count and recent alerts",
)
def get_unread_alerts(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Returns the total unread notifications count and the 5 latest unread alerts."""
    try:
        count = get_unread_notification_count(db)
        # Fetch the 5 latest unread alerts
        alerts = list_notifications(db, is_read=False, limit=5)

        latest_alerts = []
        for n in alerts:
            latest_alerts.append(
                {
                    "id": n.id,
                    "notification_type": n.notification_type,
                    "message": n.message,
                    "timestamp": n.timestamp.isoformat() if n.timestamp else None,
                }
            )

        return {
            "unread_count": count,
            "latest_alerts": latest_alerts,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/api/notifications/{notification_id}/read",
    summary="Mark single notification as read via API",
)
def mark_alert_read(
    notification_id: int, db: Session = Depends(get_db_session)
) -> dict[str, Any]:
    """Marks a single notification as read and returns success status."""
    try:
        updated = mark_notification_as_read(db, notification_id, is_read=True)
        if updated is None:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"success": True, "notification_id": notification_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
