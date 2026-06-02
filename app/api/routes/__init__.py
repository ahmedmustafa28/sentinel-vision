from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.pages import router as pages_router
from app.api.routes.stream import router as stream_router
from app.api.routes.api_notifications import router as api_notifications_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(pages_router, tags=["dashboard"])
router.include_router(stream_router, tags=["stream"])
router.include_router(api_notifications_router, tags=["notifications"])
