from __future__ import annotations

import logging
import threading
import time
from typing import Any

import cv2
import numpy as np


class CameraManager:
    """Manages a camera stream with background capture and auto-reconnect."""

    def __init__(
        self,
        source: int | str = 0,
        *,
        reconnect_interval: float = 2.0,
        max_consecutive_failures: int = 20,
        read_timeout_sleep: float = 0.01,
    ) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

        self._source: int | str = source
        self._reconnect_interval = max(reconnect_interval, 0.1)
        self._max_consecutive_failures = max(max_consecutive_failures, 1)
        self._read_timeout_sleep = max(read_timeout_sleep, 0.001)

        self._capture: cv2.VideoCapture | None = None
        self._frame_lock = threading.Lock()
        self._state_lock = threading.Lock()

        self._latest_frame: np.ndarray | None = None
        self._running = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._consecutive_failures = 0

    @property
    def source(self) -> int | str:
        return self._source

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        with self._state_lock:
            if self._running.is_set():
                self._logger.debug("Camera manager already running")
                return

            self._running.set()
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                name="camera-capture-thread",
                daemon=True,
            )
            self._capture_thread.start()
            self._logger.info(
                "Camera manager started", extra={"source": str(self._source)}
            )

    def stop(self, *, join_timeout: float = 3.0) -> None:
        with self._state_lock:
            if not self._running.is_set():
                return

            self._running.clear()

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=join_timeout)
            self._capture_thread = None

        self._release_capture()
        self._logger.info("Camera manager stopped")

    def update_source(self, source: int | str) -> None:
        """Switches the active camera source and forces reconnect."""
        with self._state_lock:
            self._source = source
            self._consecutive_failures = 0
        self._release_capture()
        self._logger.info("Camera source updated", extra={"source": str(source)})

    def get_latest_frame(self, *, copy: bool = True) -> np.ndarray | None:
        """Returns the latest captured frame for downstream modules."""
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy() if copy else self._latest_frame

    def _capture_loop(self) -> None:
        while self._running.is_set():
            try:
                if not self._is_capture_opened():
                    self._try_reconnect()
                    continue

                assert self._capture is not None
                ok, frame = self._capture.read()

                if not ok or frame is None:
                    self._consecutive_failures += 1
                    self._logger.warning(
                        "Failed to read frame",
                        extra={
                            "failures": self._consecutive_failures,
                            "source": str(self._source),
                        },
                    )

                    if self._consecutive_failures >= self._max_consecutive_failures:
                        self._logger.error(
                            "Max frame read failures reached, reconnecting",
                            extra={"source": str(self._source)},
                        )
                        self._release_capture()

                    time.sleep(self._read_timeout_sleep)
                    continue

                self._consecutive_failures = 0
                with self._frame_lock:
                    self._latest_frame = frame

            except Exception as exc:
                self._logger.exception("Unhandled error in camera loop: %s", exc)
                self._release_capture()
                time.sleep(self._reconnect_interval)

        self._release_capture()

    def _try_reconnect(self) -> None:
        try:
            self._logger.info(
                "Attempting camera connect", extra={"source": str(self._source)}
            )

            capture = cv2.VideoCapture(self._normalized_source(), cv2.CAP_FFMPEG)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(self._normalized_source())

            if not capture.isOpened():
                self._logger.error(
                    "Camera connect failed", extra={"source": str(self._source)}
                )
                time.sleep(self._reconnect_interval)
                return

            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self._capture = capture
            self._consecutive_failures = 0
            self._logger.info("Camera connected", extra={"source": str(self._source)})
        except Exception as exc:
            self._logger.error("Exception occurred during camera connection: %s", exc)
            time.sleep(self._reconnect_interval)

    def _is_capture_opened(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def _release_capture(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as exc:
                self._logger.exception("Error while releasing capture: %s", exc)
            finally:
                self._capture = None

    def _normalized_source(self) -> Any:
        source = self._source
        if isinstance(source, str):
            stripped = source.strip()
            if stripped.isdigit():
                return int(stripped)
            return stripped
        return source
