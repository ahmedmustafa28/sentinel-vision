from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.event import Event


def create_event(
    db: Session,
    *,
    event_type: str,
    camera_id: int,
    description: str | None = None,
    image_path: str | None = None,
    timestamp: datetime | None = None,
) -> Event:
    event = Event(
        event_type=event_type,
        camera_id=camera_id,
        description=description,
        image_path=image_path,
        timestamp=timestamp or datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event_by_id(db: Session, event_id: int) -> Event | None:
    return db.query(Event).filter(Event.id == event_id).first()


def list_events(
    db: Session,
    *,
    camera_id: int | None = None,
    event_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Event]:
    query = db.query(Event)

    if camera_id is not None:
        query = query.filter(Event.camera_id == camera_id)
    if event_type is not None:
        query = query.filter(Event.event_type == event_type)

    return query.order_by(Event.timestamp.desc()).offset(skip).limit(limit).all()


def delete_event(db: Session, event_id: int) -> bool:
    event = get_event_by_id(db, event_id)
    if event is None:
        return False

    db.delete(event)
    db.commit()
    return True
