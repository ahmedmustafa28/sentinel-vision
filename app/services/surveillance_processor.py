import logging
import threading
import time
import cv2
import numpy as np

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.crud_camera import list_cameras
from app.modules.yolo_detection import DetectionService
from app.modules.face_recognition import FaceRecognitionService
from app.services.event_engine import EventEngine


class SurveillanceProcessor:
    """Daemon thread worker that processes active camera streams for AI surveillance."""

    def __init__(self, camera_registry) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._settings = get_settings()
        self._camera_registry = camera_registry

        # Load Detection and Face Recognition services
        try:
            self._detection_service = DetectionService()
        except Exception as exc:
            self._logger.error(
                "Failed to load DetectionService. Visual features will be disabled: %s",
                exc,
            )
            self._detection_service = None

        try:
            self._face_recognition_service = FaceRecognitionService()
        except Exception as exc:
            self._logger.error(
                "Failed to load FaceRecognitionService. Face alerts will be disabled: %s",
                exc,
            )
            self._face_recognition_service = None

        self._event_engine = EventEngine(db_session_factory=SessionLocal)
        self._latest_annotated_frames: dict[int, np.ndarray] = {}
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Starts the background worker thread."""
        with self._lock:
            if self._running.is_set():
                return
            self._running.set()
            self._thread = threading.Thread(
                target=self._surveillance_loop,
                name="surveillance-processor",
                daemon=True,
            )
            self._thread.start()
            self._logger.info("SurveillanceProcessor background worker started")

    def stop(self) -> None:
        """Stops the background worker thread."""
        with self._lock:
            if not self._running.is_set():
                return
            self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._logger.info("SurveillanceProcessor background worker stopped")

    def get_latest_annotated_frame(self, camera_id: int) -> np.ndarray | None:
        """Gets the latest annotated frame for a camera."""
        with self._lock:
            return self._latest_annotated_frames.get(camera_id)

    def _surveillance_loop(self) -> None:
        """Main loop that queries active cameras, processes frames, and yields events."""
        target_fps = 10.0
        frame_interval = 1.0 / target_fps
        last_processed_times: dict[int, float] = {}

        while self._running.is_set():
            sweep_start = time.time()
            try:
                db = SessionLocal()
                try:
                    cameras = list_cameras(db, limit=1000)
                    active_cameras = [cam for cam in cameras if cam.is_active]
                except Exception as db_exc:
                    self._logger.error(
                        "Database connection or read error in surveillance loop: %s",
                        db_exc,
                    )
                    active_cameras = []
                finally:
                    db.close()

                if not active_cameras:
                    time.sleep(1.0)
                    continue

                for camera in active_cameras:
                    if not self._running.is_set():
                        break

                    # 1. Per-camera FPS Rate Limiting (10 FPS)
                    now = time.time()
                    last_time = last_processed_times.get(camera.id, 0.0)
                    if now - last_time < frame_interval:
                        continue
                    last_processed_times[camera.id] = now

                    try:
                        manager = self._camera_registry.get_or_create(camera.source_url)
                        frame = manager.get_latest_frame(copy=True)
                    except Exception as cam_exc:
                        self._logger.error(
                            "Failed to retrieve frame from camera %s: %s",
                            camera.id,
                            cam_exc,
                        )
                        continue

                    if frame is None:
                        continue

                    # 2. Check for motion before executing neural network inferences and pipeline
                    try:
                        motion_detected = self._event_engine._is_motion_detected(
                            camera.id, frame
                        )
                    except Exception as motion_exc:
                        self._logger.error(
                            "Motion detection calculation failed on camera %s: %s",
                            camera.id,
                            motion_exc,
                        )
                        motion_detected = True  # Fallback to True to ensure we don't miss alerts on error

                    annotated = frame.copy()
                    detections = []
                    faces = []
                    unknown_person_detected = False

                    # 3. High-Efficiency Motion Bypass: Skip inferences and DB processing when no motion is detected
                    if motion_detected:
                        # Run YOLO Object Detection
                        if self._detection_service is not None:
                            try:
                                annotated, detections = (
                                    self._detection_service.process_frame(annotated)
                                )
                            except Exception as exc:
                                self._logger.error(
                                    "YOLO prediction failure on camera %s: %s",
                                    camera.id,
                                    exc,
                                )

                        # Run Face Recognition
                        if self._face_recognition_service is not None:
                            try:
                                faces = self._face_recognition_service.recognize_faces(
                                    frame
                                )
                                annotated = (
                                    self._face_recognition_service.annotate_faces(
                                        annotated, faces
                                    )
                                )
                                unknown_person_detected = any(
                                    str(face.get("name", "Unknown")).strip().lower()
                                    == "unknown"
                                    for face in faces
                                )
                            except Exception as exc:
                                self._logger.error(
                                    "Face recognition failure on camera %s: %s",
                                    camera.id,
                                    exc,
                                )

                        # Process Event logic
                        try:
                            self._event_engine.process_frame(
                                camera_id=camera.id,
                                frame=frame,
                                detections=detections,
                                unknown_person_detected=unknown_person_detected,
                                recognized_faces=faces,
                            )
                        except Exception as exc:
                            self._logger.error(
                                "Event engine processing failure on camera %s: %s",
                                camera.id,
                                exc,
                            )
                    else:
                        # Low-CPU standby state, carry over previous overlay if available, otherwise draw standby banner
                        with self._lock:
                            prev = self._latest_annotated_frames.get(camera.id)
                        if prev is not None:
                            annotated = prev
                        else:
                            cv2.putText(
                                annotated,
                                "STANDBY - NO MOTION",
                                (20, 30),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 165, 255),
                                1,
                                cv2.LINE_AA,
                            )

                    # Cache the annotated frame for dashboard streaming
                    with self._lock:
                        self._latest_annotated_frames[camera.id] = annotated

                # Dynamic FPS sleep control based on processing latency to yield CPU slices
                elapsed = time.time() - sweep_start
                sleep_time = max(0.01, frame_interval - elapsed)
                time.sleep(sleep_time)

            except Exception as exc:
                self._logger.exception(
                    "Unhandled exception in surveillance processing loop: %s", exc
                )
                time.sleep(1.0)
