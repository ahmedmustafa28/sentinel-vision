from __future__ import annotations

import logging
import threading
from collections.abc import Iterable

from app.services.camera_manager import CameraManager


class CameraRegistry:
    """Keeps a shared pool of camera managers for multi-camera streaming."""

    def __init__(
        self,
        *,
        reconnect_interval: float = 2.0,
        max_consecutive_failures: int = 20,
        read_timeout_sleep: float = 0.01,
    ) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()
        self._managers: dict[str, CameraManager] = {}

        self._reconnect_interval = reconnect_interval
        self._max_consecutive_failures = max_consecutive_failures
        self._read_timeout_sleep = read_timeout_sleep

    def get_or_create(self, source: int | str) -> CameraManager:
        key = str(source)
        with self._lock:
            manager = self._managers.get(key)
            if manager is None:
                manager = CameraManager(
                    source=source,
                    reconnect_interval=self._reconnect_interval,
                    max_consecutive_failures=self._max_consecutive_failures,
                    read_timeout_sleep=self._read_timeout_sleep,
                )
                manager.start()
                self._managers[key] = manager
                self._logger.info("Camera manager created", extra={"source": key})

            return manager

    def sources(self) -> Iterable[str]:
        with self._lock:
            return list(self._managers.keys())

    def stop_all(self) -> None:
        with self._lock:
            managers = list(self._managers.values())
            self._managers.clear()

        for manager in managers:
            manager.stop()

        self._logger.info("All camera managers stopped")
