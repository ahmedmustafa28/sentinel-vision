"""Database package using SQLAlchemy."""

from app.db.crud_camera import (
    create_camera,
    delete_camera,
    get_camera_by_id,
    list_cameras,
    update_camera,
)
from app.db.crud_event import create_event, delete_event, get_event_by_id, list_events
from app.db.crud_known_person import (
    create_known_person,
    delete_known_person,
    get_known_person_by_id,
    list_known_persons,
    update_known_person,
)
from app.db.crud_notification import (
    create_notification,
    get_notification_by_id,
    list_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    get_unread_notification_count,
)
from app.db.init_db import initialize_database
from app.db.session import SessionLocal, engine, get_db_session

__all__ = [
    "engine",
    "SessionLocal",
    "get_db_session",
    "initialize_database",
    "create_camera",
    "get_camera_by_id",
    "list_cameras",
    "update_camera",
    "delete_camera",
    "create_event",
    "get_event_by_id",
    "list_events",
    "delete_event",
    "create_known_person",
    "get_known_person_by_id",
    "list_known_persons",
    "update_known_person",
    "delete_known_person",
    "create_notification",
    "get_notification_by_id",
    "list_notifications",
    "mark_notification_as_read",
    "mark_all_notifications_as_read",
    "get_unread_notification_count",
]
