from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func

from app.core.config import BASE_DIR
from app.db.crud_camera import create_camera, delete_camera, get_camera_by_id, list_cameras, update_camera
from app.db.crud_event import list_events
from app.db.session import SessionLocal
from app.models.event import Event

router = APIRouter()


@router.get("/", response_class=HTMLResponse, summary="Dashboard home")
def dashboard_home(request: Request):
    db = SessionLocal()
    try:
        total_cameras = len(list_cameras(db, limit=1000))
        active_cameras = len([cam for cam in list_cameras(db, limit=1000) if cam.is_active])
        recent_events = list_events(db, limit=10)

        event_counts = (
            db.query(Event.event_type, func.count(Event.id))
            .group_by(Event.event_type)
            .order_by(func.count(Event.id).desc())
            .limit(5)
            .all()
        )
    finally:
        db.close()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/index.html",
        context={
            "title": "Dashboard Overview",
            "total_cameras": total_cameras,
            "active_cameras": active_cameras,
            "recent_events": recent_events,
            "event_counts": event_counts,
        },
    )


@router.get("/events", response_class=HTMLResponse, summary="Event history page")
def event_history_page(
    request: Request,
    camera_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
):
    page_size = 20
    skip = (page - 1) * page_size

    db = SessionLocal()
    try:
        events = list_events(
            db,
            camera_id=camera_id,
            event_type=event_type if event_type else None,
            skip=skip,
            limit=page_size,
        )
        cameras = list_cameras(db, limit=1000)

        count_query = db.query(func.count(Event.id))
        if camera_id is not None:
            count_query = count_query.filter(Event.camera_id == camera_id)
        if event_type:
            count_query = count_query.filter(Event.event_type == event_type)
        total_count = int(count_query.scalar() or 0)
    finally:
        db.close()

    total_pages = max(1, (total_count + page_size - 1) // page_size)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/event_history.html",
        context={
            "title": "Event History",
            "events": events,
            "cameras": cameras,
            "camera_id": camera_id,
            "event_type": event_type or "",
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.get("/cameras", response_class=HTMLResponse, summary="Camera management page")
def camera_management_page(request: Request):
    db = SessionLocal()
    try:
        cameras = list_cameras(db, limit=1000)
        import re
        for camera in cameras:
            url = camera.source_url
            if url.startswith("rtsp://"):
                camera.source_url = re.sub(r"(rtsp://)([^:]+):([^@]+)(@)", r"\1\2:***\4", url)
    finally:
        db.close()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/camera_management.html",
        context={
            "title": "Camera Management",
            "cameras": cameras,
        },
    )


@router.post("/cameras/add", summary="Add camera")
def add_camera(
    name: str = Form(...),
    source_url: str = Form(...),
    location: str = Form(default=""),
    is_restricted: bool = Form(default=False),
):
    db = SessionLocal()
    try:
        create_camera(
            db,
            name=name.strip(),
            source_url=source_url.strip(),
            location=location.strip() or None,
            is_active=True,
            is_restricted=is_restricted,
        )
    finally:
        db.close()

    return RedirectResponse(url="/cameras", status_code=303)


@router.post("/cameras/{camera_id}/toggle", summary="Toggle camera status")
def toggle_camera(camera_id: int):
    db = SessionLocal()
    try:
        camera = get_camera_by_id(db, camera_id)
        if camera is not None:
            update_camera(db, camera_id=camera_id, is_active=not camera.is_active)
    finally:
        db.close()

    return RedirectResponse(url="/cameras", status_code=303)


@router.post("/cameras/{camera_id}/delete", summary="Delete camera")
def remove_camera(camera_id: int):
    db = SessionLocal()
    try:
        delete_camera(db, camera_id)
    finally:
        db.close()

    return RedirectResponse(url="/cameras", status_code=303)


@router.get("/reports", response_class=HTMLResponse, summary="AI reports page")
def ai_reports_page(request: Request):
    db = SessionLocal()
    try:
        total_events = int(db.query(func.count(Event.id)).scalar() or 0)
        event_breakdown = (
            db.query(Event.event_type, func.count(Event.id))
            .group_by(Event.event_type)
            .order_by(func.count(Event.id).desc())
            .all()
        )
        latest_events = list_events(db, limit=15)
    finally:
        db.close()

    reports_dir = (BASE_DIR / "data" / "reports").resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_files = sorted(
        [p for p in reports_dir.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/ai_reports.html",
        context={
            "title": "AI Reports",
            "total_events": total_events,
            "event_breakdown": event_breakdown,
            "latest_events": latest_events,
            "report_files": report_files,
        },
    )


@router.post("/cameras/{camera_id}/toggle_restricted", summary="Toggle restricted area status")
def toggle_restricted_camera(camera_id: int):
    db = SessionLocal()
    try:
        camera = get_camera_by_id(db, camera_id)
        if camera is not None:
            update_camera(db, camera_id=camera_id, is_restricted=not camera.is_restricted)
    finally:
        db.close()

    return RedirectResponse(url="/cameras", status_code=303)


@router.get("/notifications", response_class=HTMLResponse, summary="Notification history page")
def notification_history_page(
    request: Request,
    filter_type: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
):
    page_size = 20
    skip = (page - 1) * page_size

    db = SessionLocal()
    try:
        is_read = None
        if filter_type == "unread":
            is_read = False
        elif filter_type == "read":
            is_read = True

        from app.db.crud_notification import list_notifications
        notifications = list_notifications(db, is_read=is_read, skip=skip, limit=page_size)

        from sqlalchemy import func
        from app.models.notification import Notification
        count_query = db.query(func.count(Notification.id))
        if is_read is not None:
            count_query = count_query.filter(Notification.is_read == is_read)
        total_count = int(count_query.scalar() or 0)
    finally:
        db.close()

    total_pages = max(1, (total_count + page_size - 1) // page_size)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/notifications.html",
        context={
            "title": "Notifications Log",
            "notifications": notifications,
            "filter_type": filter_type,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.post("/notifications/{notification_id}/read", summary="Mark notification as read")
def read_notification(notification_id: int):
    db = SessionLocal()
    try:
        from app.db.crud_notification import mark_notification_as_read
        mark_notification_as_read(db, notification_id, is_read=True)
    finally:
        db.close()
    return RedirectResponse(url="/notifications", status_code=303)


@router.post("/notifications/read_all", summary="Mark all notifications as read")
def read_all_notifications():
    db = SessionLocal()
    try:
        from app.db.crud_notification import mark_all_notifications_as_read
        mark_all_notifications_as_read(db)
    finally:
        db.close()
    return RedirectResponse(url="/notifications", status_code=303)
