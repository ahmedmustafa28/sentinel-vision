from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.config import BASE_DIR, get_settings

# Fallback / Mock stub for face_recognition if the library is not installed
class MockFaceRecognition:
    @staticmethod
    def load_image_file(file_path):
        return np.zeros((100, 100, 3), dtype=np.uint8)

    @staticmethod
    def face_encodings(image):
        return [np.zeros((128,), dtype=np.float32)]

    @staticmethod
    def face_locations(rgb_frame, model="hog"):
        return []

    @staticmethod
    def face_distance(face_encodings, face_to_compare):
        return np.array([0.5])


try:
    import face_recognition
except ImportError:
    face_recognition = MockFaceRecognition()


class FaceRecognitionService:
    """Compares detected faces against known face images and returns identity labels."""

    def __init__(
        self,
        *,
        known_faces_dir: str | Path | None = None,
        tolerance: float | None = None,
        model: str | None = None,
    ) -> None:

        settings = get_settings()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._tolerance = (
            max(0.1, min(1.0, tolerance)) if tolerance is not None else settings.face_recognition_tolerance
        )
        self._model = model or settings.face_recognition_model

        resolved_dir = (
            Path(known_faces_dir)
            if known_faces_dir is not None
            else (BASE_DIR / settings.known_faces_dir)
        )
        self._known_faces_dir = resolved_dir.resolve()
        self._known_faces_dir.mkdir(parents=True, exist_ok=True)

        self._known_names: list[str] = []
        self._known_encodings: list[np.ndarray] = []

        self.reload_known_faces()

    @property
    def known_faces_dir(self) -> Path:
        return self._known_faces_dir

    def reload_known_faces(self) -> None:
        """Loads known faces from directory names like ali.jpg, sara.png."""
        self._known_names = []
        self._known_encodings = []

        image_paths = sorted(
            [
                p
                for p in self._known_faces_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
        )

        for image_path in image_paths:
            try:
                image = face_recognition.load_image_file(str(image_path))
                encodings = face_recognition.face_encodings(image)
                if not encodings:
                    self._logger.warning("No face found in known image", extra={"file": str(image_path)})
                    continue

                person_name = image_path.stem.strip() or "Unknown"
                self._known_names.append(person_name)
                self._known_encodings.append(encodings[0])
            except Exception as exc:
                self._logger.exception("Failed loading known face %s: %s", image_path, exc)

        self._logger.info(
            "Known faces loaded",
            extra={"count": len(self._known_names), "dir": str(self._known_faces_dir)},
        )

    def recognize_faces(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Detects faces in frame and returns name or Unknown for each face."""
        if frame is None or frame.size == 0:
            return []

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model=self._model)

        if not face_locations:
            return []

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        results: list[dict[str, Any]] = []

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            person_name = "Unknown"
            distance = None

            if self._known_encodings:
                distances = face_recognition.face_distance(self._known_encodings, face_encoding)
                if len(distances) > 0:
                    best_index = int(np.argmin(distances))
                    best_distance = float(distances[best_index])
                    distance = round(best_distance, 4)
                    if best_distance <= self._tolerance:
                        person_name = self._known_names[best_index]

            results.append(
                {
                    "name": person_name,
                    "location": {
                        "top": int(top),
                        "right": int(right),
                        "bottom": int(bottom),
                        "left": int(left),
                    },
                    "distance": distance,
                }
            )

        return results

    def annotate_faces(
        self,
        frame: np.ndarray,
        faces: list[dict[str, Any]],
    ) -> np.ndarray:
        """Draws face boxes and names on frame for preview purposes."""
        if frame is None or frame.size == 0:
            return frame

        annotated = frame.copy()
        for face in faces:
            loc = face.get("location", {})
            name = str(face.get("name", "Unknown"))

            top = int(loc.get("top", 0))
            right = int(loc.get("right", 0))
            bottom = int(loc.get("bottom", 0))
            left = int(loc.get("left", 0))

            color = (0, 180, 0) if name != "Unknown" else (0, 0, 220)
            cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
            cv2.rectangle(annotated, (left, max(0, top - 24)), (right, top), color, -1)
            cv2.putText(
                annotated,
                name,
                (left + 4, max(12, top - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return annotated

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """Runs recognition and returns annotated frame with face identity data."""
        faces = self.recognize_faces(frame)
        annotated = self.annotate_faces(frame, faces)
        return annotated, faces
