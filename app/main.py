import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.db.init_db import initialize_database
from app.services.camera_registry import CameraRegistry

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.resolved_templates_dir))

def _get_unread_count() -> int:
    try:
        from app.db.crud_notification import get_unread_notification_count
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            return get_unread_notification_count(db)
        except Exception:
            return 0
        finally:
            db.close()
    except Exception:
        return 0

templates.env.globals["get_unread_notifications_count"] = _get_unread_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application", extra={"env": settings.app_env})
    initialize_database()
    camera_registry = CameraRegistry()

    from app.services.surveillance_processor import SurveillanceProcessor
    surveillance_processor = SurveillanceProcessor(camera_registry)
    surveillance_processor.start()

    app.state.settings = settings
    app.state.templates = templates
    app.state.camera_registry = camera_registry
    app.state.surveillance_processor = surveillance_processor

    yield

    from app.services.alert_throttle import AlertThrottle
    AlertThrottle().stop()
    surveillance_processor.stop()
    camera_registry.stop_all()
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=str(settings.resolved_static_dir)), name="static")
    app.include_router(api_router)

    return app


app = create_app()

from app.core.auth import UnauthenticatedException, unauthenticated_exception_handler
app.add_exception_handler(UnauthenticatedException, unauthenticated_exception_handler)
