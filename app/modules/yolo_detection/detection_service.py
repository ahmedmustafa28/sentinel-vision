from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError as exc:  # pragma: no cover
    YOLO = None  # type: ignore[assignment]
    _ULTRALYTICS_IMPORT_ERROR = exc
else:
    _ULTRALYTICS_IMPORT_ERROR = None


class DetectionService:
    """Runs YOLO inference for selected classes and annotates frames."""

    _CLASS_CANONICAL_NAME_MAP = {
        "person": "person",
        "laptop": "laptop",
        "cell phone": "phone",
        "backpack": "bag",
        "handbag": "bag",
        "suitcase": "bag",
        "tv": "monitor",
        "monitor": "monitor",
    }

    def __init__(
        self,
        model_path: str = "data/models/yolo/yolov8n.pt",
        confidence_threshold: float = 0.45,
        iou_threshold: float = 0.50,
    ) -> None:
        if YOLO is None:
            raise ImportError(
                "ultralytics is required for DetectionService. Install dependencies first."
            ) from _ULTRALYTICS_IMPORT_ERROR

        self._logger = logging.getLogger(self.__class__.__name__)
        self._model_path = model_path
        self._confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self._iou_threshold = max(0.0, min(1.0, iou_threshold))

        resolved_model_path = Path(model_path)
        self._model = YOLO(str(resolved_model_path))

        self._logger.info(
            "Detection service initialized",
            extra={
                "model_path": str(resolved_model_path),
                "confidence_threshold": self._confidence_threshold,
                "iou_threshold": self._iou_threshold,
            },
        )

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """Runs inference, annotates frame, and returns structured detections."""
        if frame is None or frame.size == 0:
            return frame, []

        annotated_frame = frame.copy()
        detections: list[dict[str, Any]] = []

        try:
            results = self._model.predict(
                source=frame,
                conf=self._confidence_threshold,
                iou=self._iou_threshold,
                verbose=False,
            )
        except Exception as exc:
            self._logger.exception("YOLO inference failed: %s", exc)
            return annotated_frame, detections

        for result in results:
            names = result.names if hasattr(result, "names") else {}
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_idx = int(box.cls.item())
                model_class_name = names.get(cls_idx, "unknown")

                canonical_name = self._CLASS_CANONICAL_NAME_MAP.get(model_class_name)
                if canonical_name is None:
                    continue

                confidence = float(box.conf.item())
                x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]

                self._draw_detection(
                    annotated_frame=annotated_frame,
                    class_name=canonical_name,
                    confidence=confidence,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )

                detections.append(
                    {
                        "class_name": canonical_name,
                        "confidence": round(confidence, 4),
                        "bounding_box": {
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                        },
                    }
                )

        return annotated_frame, detections

    @staticmethod
    def _draw_detection(
        *,
        annotated_frame: np.ndarray,
        class_name: str,
        confidence: float,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        color = (0, 200, 0)
        label = f"{class_name} {confidence:.2f}"

        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
        cv2.rectangle(
            annotated_frame,
            (x1, max(0, y1 - 24)),
            (x1 + 220, y1),
            color,
            thickness=-1,
        )
        cv2.putText(
            annotated_frame,
            label,
            (x1 + 6, max(12, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
