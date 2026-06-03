from fastapi import APIRouter, Depends

from app.api.routes.health import router as health_router
from app.api.routes.pages import router as pages_router
from app.api.routes.stream import router as stream_router
from app.api.routes.api_notifications import router as api_notifications_router
from app.api.routes.auth import router as auth_router
from app.core.auth import get_current_user

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(auth_router, tags=["auth"])
router.include_router(pages_router, tags=["dashboard"], dependencies=[Depends(get_current_user)])
router.include_router(stream_router, tags=["stream"], dependencies=[Depends(get_current_user)])
router.include_router(api_notifications_router, tags=["notifications"], dependencies=[Depends(get_current_user)])
