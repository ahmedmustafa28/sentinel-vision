from __future__ import annotations

import logging
import re
import threading
import time
from datetime import timezone, datetime
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, get_settings
from app.db.crud_camera import create_camera, get_camera_by_id
from app.db.crud_event import create_event
from app.db.session import SessionLocal


class EventEngine:
    """Generates and persists surveillance events with duplicate prevention."""

    EVENT_PERSON_DETECTED = "person_detected"
    EVENT_UNKNOWN_PERSON_DETECTED = "unknown_person_detected"
    EVENT_OBJECT_DISAPPEARED = "object_disappeared"
    EVENT_MOTION_DETECTED = "motion_detected"
    EVENT_RESTRICTED_AREA_ENTERED = "restricted_area_entered"
    _TRACKED_REMOVAL_OBJECTS = {"laptop", "bag", "monitor"}

    def __init__(
        self,
        *,
        db_session_factory: Callable[[], Session] = SessionLocal,
        screenshot_dir: str | Path | None = None,
        dedupe_seconds: int | None = None,
        face_event_dedupe_seconds: int = 300,
        motion_min_changed_pixels: int | None = None,
        motion_min_contour_area: int | None = None,
    ) -> None:
        settings = get_settings()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._db_session_factory = db_session_factory

        resolved_screenshot_dir = (
            Path(screenshot_dir)
            if screenshot_dir is not None
            else (BASE_DIR / settings.event_snapshot_dir).resolve()
        )
        resolved_screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._screenshot_dir = resolved_screenshot_dir
        self._dedupe_seconds = max(
            1,
            (
                dedupe_seconds
                if dedupe_seconds is not None
                else settings.event_dedupe_seconds
            ),
        )
        self._object_disappearance_seconds = max(
            1, settings.object_disappearance_seconds
        )
        self._face_event_dedupe_seconds = max(1, face_event_dedupe_seconds)
        self._motion_min_changed_pixels = max(
            1,
            (
                motion_min_changed_pixels
                if motion_min_changed_pixels is not None
                else settings.motion_min_changed_pixels
            ),
        )
        self._motion_min_contour_area = max(
            1,
            (
                motion_min_contour_area
                if motion_min_contour_area is not None
                else settings.motion_min_contour_area
            ),
        )

        self._last_event_epoch: dict[str, float] = {}
        self._previous_gray_frame_by_camera: dict[int, np.ndarray] = {}
        self._tracked_object_state: dict[int, dict[str, dict[str, float | bool]]] = {}
        self._lock = threading.Lock()

    def process_frame(
        self,
        *,
        camera_id: int,
        frame: np.ndarray,
        detections: list[dict[str, Any]] | None,
        unknown_person_detected: bool = False,
        recognized_faces: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generates events from the current frame and persists them."""
        detections = detections or []
        recognized_faces = recognized_faces or []
        generated_events: list[dict[str, Any]] = []

        generated_events.extend(
            self._process_face_recognition_events(
                camera_id=camera_id,
                frame=frame,
                recognized_faces=recognized_faces,
            )
        )

        current_labels = {
            str(item.get("class_name", "")).strip().lower()
            for item in detections
            if item.get("class_name")
        }

        # Check if the camera monitors a restricted area
        db_cam = self._db_session_factory()
        is_restricted = False
        try:
            camera = get_camera_by_id(db_cam, camera_id)
            if camera is not None:
                is_restricted = bool(camera.is_restricted)
        finally:
            db_cam.close()

        if "person" in current_labels:
            event = self._create_event_if_allowed(
                camera_id=camera_id,
                event_type=self.EVENT_PERSON_DETECTED,
                description="Person detected in camera view.",
                frame=frame,
                dedupe_key=f"{camera_id}:{self.EVENT_PERSON_DETECTED}",
            )
            if event is not None:
                generated_events.append(event)

            if is_restricted:
                event_rest = self._create_event_if_allowed(
                    camera_id=camera_id,
                    event_type=self.EVENT_RESTRICTED_AREA_ENTERED,
                    description="Restricted area entered - unauthorized person detected.",
                    frame=frame,
                    dedupe_key=f"{camera_id}:{self.EVENT_RESTRICTED_AREA_ENTERED}",
                    dedupe_seconds=self._dedupe_seconds,
                )
                if event_rest is not None:
                    generated_events.append(event_rest)

        if unknown_person_detected:
            event = self._create_event_if_allowed(
                camera_id=camera_id,
                event_type=self.EVENT_UNKNOWN_PERSON_DETECTED,
                description="Unknown person detected in camera view.",
                frame=frame,
                dedupe_key=f"{camera_id}:{self.EVENT_UNKNOWN_PERSON_DETECTED}",
                dedupe_seconds=self._dedupe_seconds,
            )
            if event is not None:
                generated_events.append(event)

        removal_events = self._compute_object_removal_events(camera_id, current_labels)
        for label in removal_events:
            if label == "laptop":
                description = "Possible laptop removal detected"
            elif label == "bag":
                description = "Possible bag removal detected"
            else:
                description = "Possible monitor removal detected"

            event = self._create_event_if_allowed(
                camera_id=camera_id,
                event_type=self.EVENT_OBJECT_DISAPPEARED,
                description=description,
                frame=frame,
                dedupe_key=f"{camera_id}:{self.EVENT_OBJECT_DISAPPEARED}:removal:{label}",
                dedupe_seconds=self._dedupe_seconds,
            )
            if event is not None:
                generated_events.append(event)

        if self._is_motion_detected(camera_id, frame):
            event = self._create_event_if_allowed(
                camera_id=camera_id,
                event_type=self.EVENT_MOTION_DETECTED,
                description="Motion detected in camera view.",
                frame=frame,
                dedupe_key=f"{camera_id}:{self.EVENT_MOTION_DETECTED}",
                dedupe_seconds=self._dedupe_seconds,
            )
            if event is not None:
                generated_events.append(event)

        return generated_events

    def _compute_object_removal_events(
        self, camera_id: int, current_labels: set[str]
    ) -> list[str]:
        now = time.time()
        tracked_now = current_labels.intersection(self._TRACKED_REMOVAL_OBJECTS)

        with self._lock:
            camera_state = self._tracked_object_state.setdefault(camera_id, {})
            for label in self._TRACKED_REMOVAL_OBJECTS:
                state = camera_state.setdefault(
                    label,
                    {
                        "was_seen": False,
                        "last_seen": 0.0,
                        "alerted": False,
                    },
                )

                if label in tracked_now:
                    state["was_seen"] = True
                    state["last_seen"] = now
                    state["alerted"] = False

            removal_events: list[str] = []
            for label in sorted(self._TRACKED_REMOVAL_OBJECTS):
                state = camera_state[label]
                was_seen = bool(state["was_seen"])
                last_seen = float(state["last_seen"])
                alerted = bool(state["alerted"])

                if not was_seen:
                    continue

                if label in tracked_now:
                    continue

                disappeared_for = now - last_seen
                if (
                    disappeared_for >= float(self._object_disappearance_seconds)
                    and not alerted
                ):
                    state["alerted"] = True
                    removal_events.append(label)

        return removal_events

    def _is_motion_detected(self, camera_id: int, frame: np.ndarray) -> bool:
        if frame is None or frame.size == 0:
            return False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        with self._lock:
            previous = self._previous_gray_frame_by_camera.get(camera_id)
            self._previous_gray_frame_by_camera[camera_id] = gray

        if previous is None:
            return False

        frame_delta = cv2.absdiff(previous, gray)
        threshold = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        threshold = cv2.dilate(threshold, None, iterations=2)

        changed_pixels = int(cv2.countNonZero(threshold))
        contours, _ = cv2.findContours(
            threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        largest_contour_area = max((cv2.contourArea(c) for c in contours), default=0.0)

        return (
            changed_pixels >= self._motion_min_changed_pixels
            and largest_contour_area >= float(self._motion_min_contour_area)
        )

    def _process_face_recognition_events(
        self,
        *,
        camera_id: int,
        frame: np.ndarray,
        recognized_faces: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        generated_events: list[dict[str, Any]] = []

        for face in recognized_faces:
            raw_name = str(face.get("name", "Unknown")).strip()
            name = raw_name or "Unknown"

            if name.lower() == "unknown":
                event = self._create_event_if_allowed(
                    camera_id=camera_id,
                    event_type=self.EVENT_UNKNOWN_PERSON_DETECTED,
                    description="Unknown individual detected",
                    frame=frame,
                    dedupe_key=f"{camera_id}:{self.EVENT_UNKNOWN_PERSON_DETECTED}:unknown",
                    dedupe_seconds=self._face_event_dedupe_seconds,
                )
            else:
                event = self._create_event_if_allowed(
                    camera_id=camera_id,
                    event_type=self.EVENT_PERSON_DETECTED,
                    description=f"{name} entered the room",
                    frame=frame,
                    dedupe_key=f"{camera_id}:{self.EVENT_PERSON_DETECTED}:{name.lower()}",
                    dedupe_seconds=self._face_event_dedupe_seconds,
                )

            if event is not None:
                generated_events.append(event)

        return generated_events

    def _create_event_if_allowed(
        self,
        *,
        camera_id: int,
        event_type: str,
        description: str,
        frame: np.ndarray,
        dedupe_key: str,
        dedupe_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        if not self._should_emit(dedupe_key, dedupe_seconds=dedupe_seconds):
            return None

        image_path = self._save_event_screenshot(
            camera_id=camera_id,
            event_type=event_type,
            frame=frame,
        )

        db = self._db_session_factory()
        try:
            self._ensure_camera_exists(db=db, camera_id=camera_id)
            created = create_event(
                db,
                event_type=event_type,
                camera_id=camera_id,
                description=description,
                image_path=image_path,
            )

            try:
                from app.services.notification_service import NotificationService

                notifier = NotificationService()
                notifier.process_event(db, created)
            except Exception as e_error:
                self._logger.error("Failed to process event notifications: %s", e_error)

            return {
                "id": created.id,
                "timestamp": (
                    created.timestamp.isoformat() if created.timestamp else None
                ),
                "event_type": created.event_type,
                "description": created.description,
                "camera_id": created.camera_id,
                "image_path": created.image_path,
            }
        except Exception as exc:
            self._logger.exception("Failed to create event: %s", exc)
            return None
        finally:
            db.close()

    def _should_emit(
        self, dedupe_key: str, *, dedupe_seconds: int | None = None
    ) -> bool:
        now = time.time()
        effective_dedupe_seconds = float(dedupe_seconds or self._dedupe_seconds)

        with self._lock:
            last = self._last_event_epoch.get(dedupe_key)
            if last is not None and (now - last) < effective_dedupe_seconds:
                return False

            self._last_event_epoch[dedupe_key] = now
            return True

    def _save_event_screenshot(
        self, *, camera_id: int, event_type: str, frame: np.ndarray
    ) -> str | None:
        if frame is None or frame.size == 0:
            return None

        safe_event_type = re.sub(r"[^a-zA-Z0-9_-]+", "_", event_type.strip().lower())
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        file_name = f"cam{camera_id}_{safe_event_type}_{timestamp}.jpg"
        file_path = self._screenshot_dir / file_name

        try:
            ok = cv2.imwrite(str(file_path), frame)
            if not ok:
                self._logger.error(
                    "Failed to write event screenshot", extra={"file": str(file_path)}
                )
                return None
        except Exception as exc:
            self._logger.exception("Error saving event screenshot: %s", exc)
            return None

        return str(file_path)

    @staticmethod
    def _ensure_camera_exists(*, db: Session, camera_id: int) -> None:
        existing = get_camera_by_id(db, camera_id)
        if existing is not None:
            return

        create_camera(
            db,
            name=f"Camera {camera_id}",
            source_url=str(camera_id),
            location="Auto-registered",
            is_active=True,
        )
