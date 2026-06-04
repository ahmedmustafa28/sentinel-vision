import logging

from sqlalchemy import text

from app.db.session import engine
from app.models.base import Base

logger = logging.getLogger(__name__)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        # Lightweight migrations to add new columns if they do not exist
        try:
            connection.execute(
                text(
                    "ALTER TABLE notifications ADD COLUMN retry_count INTEGER DEFAULT 0 NOT NULL"
                )
            )
            logger.info("Migrated notifications table: added retry_count column")
        except Exception:
            pass  # Column already exists or table doesn't exist yet

        try:
            connection.execute(
                text(
                    "ALTER TABLE notifications ADD COLUMN status VARCHAR(50) DEFAULT 'PENDING' NOT NULL"
                )
            )
            logger.info("Migrated notifications table: added status column")
        except Exception:
            pass  # Column already exists

        # Force commit the connection if in autocommit or execute it safely
        try:
            connection.commit()
        except Exception:
            pass

        connection.execute(text("SELECT 1"))

    logger.info("Database initialized successfully")
