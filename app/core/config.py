from functools import lru_cache
import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_host: str
    app_port: int
    debug: bool
    secret_key: str
    db_url: str
    db_echo: bool
    static_dir: str
    templates_dir: str
    log_level: str
    log_format: str
    default_camera_source: str
    stream_fps: int
    event_snapshot_dir: str
    event_dedupe_seconds: int
    object_disappearance_seconds: int
    motion_min_changed_pixels: int
    motion_min_contour_area: int
    known_faces_dir: str
    face_recognition_tolerance: float
    face_recognition_model: str
    report_output_dir: str
    ollama_base_url: str
    ollama_model: str
    report_llm_temperature: float
    enable_email_alerts: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    alert_to_email: str
    alert_cooldown_seconds: int
    alert_digest_minutes: int | None
    allow_local_rtsp: bool
    event_retention_days: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "AI CCTV Surveillance"),
            app_env=os.getenv("APP_ENV", "development"),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=_to_int(os.getenv("APP_PORT"), 8000),
            debug=_to_bool(os.getenv("DEBUG"), False),
            secret_key=os.getenv("SECRET_KEY", "change-me"),
            db_url=os.getenv("DB_URL", "sqlite:///./data/sqlite/cctv.db"),
            db_echo=_to_bool(os.getenv("DB_ECHO"), False),
            static_dir=os.getenv("STATIC_DIR", "app/static"),
            templates_dir=os.getenv("TEMPLATES_DIR", "app/templates"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv(
                "LOG_FORMAT", "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ),
            default_camera_source=os.getenv("DEFAULT_CAMERA_SOURCE", "0"),
            stream_fps=_to_int(os.getenv("STREAM_FPS"), 20),
            event_snapshot_dir=os.getenv("EVENT_SNAPSHOT_DIR", "./data/snapshots"),
            event_dedupe_seconds=_to_int(os.getenv("EVENT_DEDUPE_SECONDS"), 10),
            object_disappearance_seconds=_to_int(
                os.getenv("OBJECT_DISAPPEARANCE_SECONDS"), 30
            ),
            motion_min_changed_pixels=_to_int(
                os.getenv("MOTION_MIN_CHANGED_PIXELS"), 2500
            ),
            motion_min_contour_area=_to_int(os.getenv("MOTION_MIN_CONTOUR_AREA"), 1200),
            known_faces_dir=os.getenv("KNOWN_FACES_DIR", "known_faces"),
            face_recognition_tolerance=float(os.getenv("FACE_TOLERANCE", "0.5")),
            face_recognition_model=os.getenv("FACE_MODEL", "hog"),
            report_output_dir=os.getenv("REPORT_OUTPUT_DIR", "./data/reports"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
            report_llm_temperature=float(os.getenv("REPORT_LLM_TEMPERATURE", "0.2")),
            enable_email_alerts=_to_bool(os.getenv("ENABLE_EMAIL_ALERTS"), False),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=_to_int(os.getenv("SMTP_PORT"), 587),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_pass=os.getenv("SMTP_PASS", ""),
            alert_to_email=os.getenv("ALERT_TO_EMAIL")
            or os.getenv("SMTP_TO_EMAIL")
            or "",
            alert_cooldown_seconds=_to_int(os.getenv("ALERT_COOLDOWN_SECONDS"), 60),
            alert_digest_minutes=_to_int(os.getenv("ALERT_DIGEST_MINUTES"), 0) or None,
            allow_local_rtsp=_to_bool(os.getenv("ALLOW_LOCAL_RTSP"), False),
            event_retention_days=_to_int(os.getenv("EVENT_RETENTION_DAYS"), 30),
        )

    @property
    def resolved_static_dir(self) -> Path:
        return BASE_DIR / self.static_dir

    @property
    def resolved_templates_dir(self) -> Path:
        return BASE_DIR / self.templates_dir


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
