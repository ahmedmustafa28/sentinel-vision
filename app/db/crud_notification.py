from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    event_id: int | None = None,
    notification_type: str,
    message: str,
    email_sent: bool = False,
    email_recipient: str | None = None,
) -> Notification:
    notification = Notification(
        event_id=event_id,
        notification_type=notification_type,
        message=message,
        email_sent=email_sent,
        email_recipient=email_recipient,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notification_by_id(db: Session, notification_id: int) -> Notification | None:
    return db.query(Notification).filter(Notification.id == notification_id).first()


def list_notifications(
    db: Session,
    *,
    is_read: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Notification]:
    query = db.query(Notification)
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    return query.order_by(Notification.timestamp.desc()).offset(skip).limit(limit).all()


def mark_notification_as_read(db: Session, notification_id: int, is_read: bool = True) -> Notification | None:
    notification = get_notification_by_id(db, notification_id)
    if notification is None:
        return None
    notification.is_read = is_read
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_notifications_as_read(db: Session) -> int:
    result = db.query(Notification).filter(Notification.is_read == False).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return result


def get_unread_notification_count(db: Session) -> int:
    return int(db.query(func.count(Notification.id)).filter(Notification.is_read == False).scalar() or 0)
