from datetime import datetime, timezone
import logging
from sqlalchemy import text
from typing import Any

from app.core.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger("app.services.health_service")
settings = get_settings()


def health_status(processor: Any = None, registry: Any = None) -> dict[str, Any]:
    """Inspects and returns system health status for cameras, models, database, and background processing."""
    status = "healthy"
    checks = {}

    # 1. Database connection check
    db_ok = False
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception as exc:
        logger.error("Health check - Database connection failed: %s", exc)

    checks["database_connected"] = "healthy" if db_ok else "unhealthy"
    if not db_ok:
        status = "unhealthy"

    # 2. Camera connection status check
    camera_health = "healthy"
    camera_details = []
    
    active_cameras_count = 0
    connected_cameras_count = 0
    
    try:
        db = SessionLocal()
        try:
            from app.db.crud_camera import list_cameras
            cameras = list_cameras(db, limit=1000)
            active_cameras = [c for c in cameras if c.is_active]
            active_cameras_count = len(active_cameras)
            
            for cam in active_cameras:
                cam_status = "disconnected"
                if registry is not None:
                    # Registry tracks cameras by string of source_url
                    manager = registry._managers.get(str(cam.source_url))
                    if manager is not None and manager.is_running:
                        latest_frame = manager.get_latest_frame(copy=False)
                        if latest_frame is not None:
                            cam_status = "connected"
                            connected_cameras_count += 1
                
                camera_details.append({
                    "id": cam.id,
                    "name": cam.name,
                    "source": cam.source_url,
                    "status": cam_status
                })
        finally:
            db.close()
    except Exception as exc:
        logger.error("Health check - Camera state inspection failed: %s", exc)
        camera_health = "unhealthy"

    if active_cameras_count > 0:
        if connected_cameras_count == 0:
            camera_health = "unhealthy"
        elif connected_cameras_count < active_cameras_count:
            camera_health = "degraded"

    checks["camera_connection"] = {
        "status": camera_health,
        "active_count": active_cameras_count,
        "connected_count": connected_cameras_count,
        "cameras": camera_details
    }
    
    if camera_health == "unhealthy" and status == "healthy":
        status = "unhealthy"
    elif camera_health == "degraded" and status == "healthy":
        status = "degraded"

    # 3. YOLO model loaded check
    yolo_ok = False
    if processor is not None and processor._detection_service is not None:
        if getattr(processor._detection_service, "_model", None) is not None:
            yolo_ok = True

    checks["yolo_model_loaded"] = "healthy" if yolo_ok else "unhealthy"
    if not yolo_ok and status == "healthy":
        status = "degraded"

    # 4. Face recognition module loaded check
    face_ok = False
    if processor is not None and processor._face_recognition_service is not None:
        face_ok = True

    checks["face_recognition_loaded"] = "healthy" if face_ok else "unhealthy"
    if not face_ok and status == "healthy":
        status = "degraded"

    # 5. Event engine running check
    engine_ok = False
    if processor is not None and processor._event_engine is not None:
        engine_ok = True

    checks["event_engine_running"] = "healthy" if engine_ok else "unhealthy"
    if not engine_ok and status == "healthy":
        status = "degraded"

    # Surveillance processor daemon thread check
    worker_running = False
    if processor is not None and processor._running is not None:
        if processor._running.is_set() and processor._thread is not None and processor._thread.is_alive():
            worker_running = True

    checks["surveillance_processor_running"] = "healthy" if worker_running else "unhealthy"
    if not worker_running and status == "healthy":
        status = "degraded"

    # Alert throttle state check
    import time
    from app.services.alert_throttle import AlertThrottle
    throttle = AlertThrottle()
    
    current_time = time.time()
    cooldowns_list = []
    cooldown_seconds = throttle.settings.alert_cooldown_seconds
    
    for (camera_id, event_type), last_fired in list(throttle.cooldowns.items()):
        elapsed = current_time - last_fired
        remaining = cooldown_seconds - elapsed
        if remaining > 0:
            cooldowns_list.append({
                "camera_id": camera_id,
                "event_type": event_type,
                "remaining_seconds": round(remaining, 2)
            })
            
    checks["alert_throttle"] = {
        "cooldowns": cooldowns_list
    }

    return {
        "status": status,
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks
    }
