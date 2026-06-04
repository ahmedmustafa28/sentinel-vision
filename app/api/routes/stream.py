from __future__ import annotations

import time
from collections.abc import Generator

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db.crud_camera import get_camera_by_id
from app.db.session import SessionLocal

router = APIRouter()


def _placeholder_frame(width: int = 640, height: int = 360) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (20, 20, 20)
    cv2.putText(
        frame,
        "Waiting for video stream...",
        (40, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def _encode_jpeg(frame: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("Failed to encode frame")
    return encoded.tobytes()


def _stream_generator(
    manager,
    surveillance_processor=None,
    camera_id: int | None = None,
    fps: int = 20,
) -> Generator[bytes, None, None]:
    frame_interval = 1.0 / max(fps, 1)

    while True:
        frame = None
        if surveillance_processor is not None and camera_id is not None:
            frame = surveillance_processor.get_latest_annotated_frame(camera_id)

        if frame is None:
            frame = manager.get_latest_frame(copy=False)

        if frame is None:
            frame = _placeholder_frame()

        try:
            jpeg = _encode_jpeg(frame)
        except Exception:
            time.sleep(frame_interval)
            continue

        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")

        time.sleep(frame_interval)


def _resolve_source(camera_id: int | None, source: str | None) -> int | str:
    if camera_id is not None:
        db: Session = SessionLocal()
        try:
            camera = get_camera_by_id(db, camera_id)
            if camera is None:
                raise HTTPException(status_code=404, detail="Camera not found")
            return camera.source_url
        finally:
            db.close()

    if source is None or source.strip() == "":
        return 0

    return source.strip()


@router.get("/video_feed", summary="Live MJPEG stream")
def video_feed(
    request: Request,
    camera_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
):
    resolved_source = _resolve_source(camera_id, source)
    camera_registry = request.app.state.camera_registry
    manager = camera_registry.get_or_create(resolved_source)

    surveillance_processor = getattr(request.app.state, "surveillance_processor", None)
    settings = request.app.state.settings
    return StreamingResponse(
        _stream_generator(
            manager,
            surveillance_processor=surveillance_processor,
            camera_id=camera_id,
            fps=settings.stream_fps,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/live", response_class=HTMLResponse, summary="Live stream page")
def live_page(
    request: Request,
    camera_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    effective_source = source if source is not None else settings.default_camera_source

    return templates.TemplateResponse(
        request=request,
        name="pages/live.html",
        context={
            "title": "Live Stream",
            "camera_id": camera_id,
            "source": effective_source,
        },
    )
