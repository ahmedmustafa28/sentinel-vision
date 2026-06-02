from pathlib import Path
from collections.abc import Generator
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import OperationalError

from app.core.config import BASE_DIR, get_settings


settings = get_settings()

if settings.db_url.startswith("sqlite:///"):
    sqlite_path = settings.db_url.replace("sqlite:///", "", 1)
    if sqlite_path.startswith("./"):
        db_file = BASE_DIR / sqlite_path[2:]
        db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.db_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # 30 seconds driver-level busy timeout
    } if settings.db_url.startswith("sqlite") else {},
    echo=settings.db_echo,
    future=True,
)

# Enable WAL mode and set busy_timeout for SQLite connection pool
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds busy timeout
        except Exception:
            pass
        finally:
            cursor.close()

# Enforce BEGIN IMMEDIATE to serialize write transactions immediately and avoid deadlocks
@event.listens_for(engine, "begin")
def do_begin(conn):
    if settings.db_url.startswith("sqlite"):
        conn.exec_driver_sql("BEGIN IMMEDIATE")


class RetryingSession(Session):
    """Custom SQLAlchemy Session that automatically retries commits on SQLite busy/locked errors."""

    def commit(self) -> None:
        max_retries = 3
        backoff_factor = 0.1
        for attempt in range(max_retries):
            try:
                super().commit()
                return
            except OperationalError as exc:
                self.rollback()
                if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                    if attempt < max_retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                raise exc
            except Exception as exc:
                self.rollback()
                raise exc


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=RetryingSession)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from contextlib import contextmanager

@contextmanager
def db_session_context() -> Generator[Session, None, None]:
    """Provides a thread-safe transaction context that ensures proper commit/rollback and closure."""
    db = SessionLocal()
    try:
        yield db
        # RetryingSession commit handles auto-retries internally
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def commit_with_retry(db: Session, max_retries: int = 3, backoff_factor: float = 0.1) -> None:
    """Commits a transaction, leveraging RetryingSession's automatic commit retry mechanism."""
    db.commit()
