"""Camera capture manager for eye tracking system.

This module provides a threaded camera capture system that continuously reads
frames from an OpenCV VideoCapture source and delivers them to registered
callback functions. It manages frame timing to achieve a target FPS and runs
capture in a background thread to avoid blocking the main application.

The Camera class is designed to be robust, handling capture failures gracefully
and providing clean start/stop semantics for resource management.

"""

import logging
import threading
import time
from typing import Callable, List

import cv2
import numpy as np


class Camera:
    """Threaded camera capture manager for continuous frame delivery.

    Attributes:
        capture (cv2.VideoCapture): OpenCV video capture source.
        fps (float): Target frames per second for capture.
        callbacks (List[Callable[[np.ndarray], None]]): Registered frame callbacks.
        logger (logging.Logger): Logger instance for this camera.
        _thread (Optional[threading.Thread]): Background capture thread.
        _running (bool): Flag indicating whether capture is active.
        _stop_event (threading.Event): Event to signal capture thread to stop.
    """

    def __init__(self, capture: cv2.VideoCapture, fps: float) -> None:
        """Initialize camera capture manager.

        Args:
            capture: OpenCV VideoCapture object for the camera source.
                Must be opened before passing to this constructor.
            fps: Target frames per second for capturing. Must be positive.
                The actual frame rate may be lower if capture or processing
                is slower than this target.

        Raises:
            ValueError: If fps is not positive.
        """
        if fps <= 0:
            raise ValueError(f"FPS must be positive, got {fps}")

        self.capture: cv2.VideoCapture = capture
        self.fps: float = fps
        self.callbacks: List[Callable[[np.ndarray], None]] = []
        self.logger: logging.Logger = logging.getLogger(__name__)

        self._thread: threading.Thread | None = None
        self._running: bool = False
        self._stop_event: threading.Event = threading.Event()

    def register_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        self.callbacks.append(callback)
        self.logger.debug(f"Registered callback: {callback.__name__}")

    def start(self) -> None:
        if self._running:
            self.logger.warning("Camera already started, ignoring start() call")
            return

        if not self.capture.isOpened():
            raise RuntimeError("VideoCapture is not opened")

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"Camera capture started at {self.fps} FPS")

    def stop(self) -> None:
        if not self._running:
            self.logger.debug("Camera not running, ignoring stop() call")
            return

        self.logger.info("Stopping camera capture...")
        self._stop_event.set()
        self._running = False

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                self.logger.warning("Capture thread did not stop within timeout")
            else:
                self.logger.info("Camera capture stopped")

        self._thread = None
        self.capture.release()

    def _capture_loop(self) -> None:
        frame_interval = 1.0 / self.fps
        self.logger.debug(f"Capture loop started (interval: {frame_interval:.3f}s)")

        while not self._stop_event.is_set():
            start_time = time.time()

            ret, frame = self.capture.read()
            frame = frame[:,:,::-1]
            frame = cv2.flip(frame, 1)

            if not ret:
                self.logger.warning("Failed to read frame from camera, continuing...")
                self._stop_event.wait(frame_interval)
                continue

            for callback in self.callbacks:
                try:
                    callback(frame)
                except Exception as e:
                    self.logger.error(
                        f"Callback {callback.__name__} raised exception: {e}",
                        exc_info=True,
                    )

            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed

            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

        self.logger.debug("Capture loop exited")
