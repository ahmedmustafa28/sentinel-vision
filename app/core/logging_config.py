import logging
from logging.config import dictConfig
from pathlib import Path

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_level = settings.log_level.upper()

    # Automatically ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "format": "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "level": log_level,
            },
            "camera_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/camera.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "formatter": "structured",
                "level": log_level,
                "encoding": "utf-8",
            },
            "events_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/events.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "formatter": "structured",
                "level": log_level,
                "encoding": "utf-8",
            },
            "ai_processing_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/ai_processing.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "formatter": "structured",
                "level": log_level,
                "encoding": "utf-8",
            },
            "api_requests_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/api_requests.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "formatter": "structured",
                "level": log_level,
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
        "loggers": {
            # Camera operations
            "app.services.camera_manager": {
                "handlers": ["camera_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "app.services.camera_registry": {
                "handlers": ["camera_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            # Events, alerts, notifications
            "app.services.event_engine": {
                "handlers": ["events_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "app.services.notification_service": {
                "handlers": ["events_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "app.db.crud_event": {
                "handlers": ["events_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "app.db.crud_notification": {
                "handlers": ["events_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            # AI Processing (YOLO, Face Recognition, Surveillance Loop)
            "app.modules.yolo_detection": {
                "handlers": ["ai_processing_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "app.modules.face_recognition": {
                "handlers": ["ai_processing_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "app.services.surveillance_processor": {
                "handlers": ["ai_processing_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            # API Requests
            "app.api": {
                "handlers": ["api_requests_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["api_requests_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["api_requests_file", "console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["api_requests_file", "console"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

    dictConfig(config)
    logging.getLogger(__name__).info("Structured and separated logging system configured successfully", extra={"level": log_level})
