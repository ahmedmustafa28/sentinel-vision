import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.base import Base
from app.models.camera import Camera
from app.models.event import Event
from app.models.notification import Notification

def seed_data():
    settings = get_settings()
    
    # Resolve exact database path in project folder (parents[1] is the project root)
    project_root = Path(__file__).resolve().parents[1]
    db_file_path = project_root / "data" / "sqlite" / "cctv.db"
    
    print(f"Target database file: {db_file_path}")

    # Delete existing database file to start completely fresh with all columns and constraints
    db_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Safely delete old database and its journals
    for suffix in ["", "-wal", "-shm", "-journal"]:
        f_path = db_file_path.parent / (db_file_path.name + suffix)
        if f_path.exists():
            try:
                f_path.unlink()
                print(f"Deleted old database asset: {f_path}")
            except Exception as e:
                print(f"Could not delete asset {f_path}: {e}")

    engine = create_engine(settings.db_url)
    
    # Run initialize_database to create everything cleanly
    from app.db.init_db import initialize_database
    initialize_database()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        now = datetime.now(timezone.utc)

        # 1. Add Mock Cameras
        cam1 = Camera(
            name="Front Lobby Gate",
            source_url="0",  # default webcam source
            location="Lobby Entrance",
            is_active=True,
            is_restricted=False,
        )
        cam2 = Camera(
            name="Server Vault Room",
            source_url="rtsp://mock-server-vault",
            location="Building Vault",
            is_active=True,
            is_restricted=True,  # Restricted area!
        )
        db.add_all([cam1, cam2])
        db.commit()
        print("Mock cameras seeded successfully.")

        # 2. Add Mock Events
        # Standard Person Detections on Front Lobby (Non-restricted)
        e1 = Event(
            camera_id=cam1.id,
            event_type="person_detected",
            description="Person detected at Lobby Entrance.",
            timestamp=now - timedelta(minutes=45),
            image_path=None
        )
        # Restricted Area Entry on Server Vault Room
        e2 = Event(
            camera_id=cam2.id,
            event_type="restricted_area_entered",
            description="Restricted Area Entry: Unauthorized individual detected in Server Vault.",
            timestamp=now - timedelta(minutes=30),
            image_path=None
        )
        # Unknown face seen in Server Vault Room
        e3 = Event(
            camera_id=cam2.id,
            event_type="unknown_person_detected",
            description="Unknown face detected at building vault camera.",
            timestamp=now - timedelta(minutes=15),
            image_path=None
        )
        # Object Removal alert in Server Vault Room
        e4 = Event(
            camera_id=cam2.id,
            event_type="object_disappeared",
            description="Critical Asset Warning: Main backup laptop missing from server shelf.",
            timestamp=now - timedelta(minutes=5),
            image_path=None
        )
        db.add_all([e1, e2, e3, e4])
        db.commit()
        print("Mock events seeded successfully.")

        # 3. Add Mock Notifications (Alerts) corresponding to critical events
        n1 = Notification(
            event_id=e2.id,
            notification_type="restricted_area_entered",
            message="Restricted Area Entry Alert: Unauthorized individual detected inside Building Vault by camera 'Server Vault Room'.",
            email_sent=True,
            email_recipient="admin@sentinel.local",
            is_read=False,  # Unread
            retry_count=0,
            status="SENT",
            timestamp=e2.timestamp
        )
        n2 = Notification(
            event_id=e3.id,
            notification_type="unknown_person_detected",
            message="Intrusion Warning: Unknown individual identified near Vault by camera 'Server Vault Room'.",
            email_sent=True,
            email_recipient="admin@sentinel.local",
            is_read=False,  # Unread
            retry_count=0,
            status="SENT",
            timestamp=e3.timestamp
        )
        n3 = Notification(
            event_id=e4.id,
            notification_type="object_disappeared",
            message="Critical Theft Alarm: Main backup laptop disappeared from server shelf at Building Vault.",
            email_sent=False,
            email_recipient=None,
            is_read=False,  # Unread
            retry_count=3,
            status="FAILED",  # Tested retry failure!
            timestamp=e4.timestamp
        )
        db.add_all([n1, n2, n3])
        db.commit()
        print("Mock notifications seeded successfully.")
        print("Seeding completed. Database ready for live preview.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
