from fastapi import APIRouter, Request

from app.services.health_service import health_status

router = APIRouter()


@router.get("/health", summary="Service health check")
def get_health(request: Request):
    app = request.app
    processor = getattr(app.state, "surveillance_processor", None)
    registry = getattr(app.state, "camera_registry", None)
    scheduler = getattr(app.state, "scheduler", None)
    return health_status(processor=processor, registry=registry, scheduler=scheduler)


@router.get("/api/health", summary="Service health check (legacy/API)")
def get_health_api(request: Request):
    app = request.app
    processor = getattr(app.state, "surveillance_processor", None)
    registry = getattr(app.state, "camera_registry", None)
    scheduler = getattr(app.state, "scheduler", None)
    return health_status(processor=processor, registry=registry, scheduler=scheduler)
