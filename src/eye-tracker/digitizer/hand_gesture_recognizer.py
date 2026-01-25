"""Hand gesture recognition for touchless HID control.

This module provides real-time hand gesture recognition using computer vision
techniques. It processes video frames to detect and classify hand gestures
that control mouse actions in the touchless HID digitizer system.

The HandGestureRecognizer class is designed to be integrated into the digitizer
pipeline, processing camera frames and returning recognized gesture types that
can be translated into HID commands.

Uses MediaPipe Tasks Hand Landmarker to detect finger-thumb touch gestures:
- Primary button: Thumb tip touches index finger tip
- Secondary button: Thumb tip touches middle finger tip
- Tertiary button: Thumb tip touches ring finger tip
"""

import logging
import urllib.request
from pathlib import Path
from typing import Any, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

from gesture_types import GestureType


class HandGestureRecognizer:
    """Recognizes hand gestures from video frames.

    Processes camera frames to detect and classify hand gestures for touchless
    mouse control. This class maintains internal state for gesture tracking
    and provides a simple interface for frame-by-frame processing.

    Uses MediaPipe Tasks Hand Landmarker to detect finger-thumb touch gestures
    based on distance between landmark points in normalized coordinates.

    Attributes:
        touch_threshold: Maximum distance between thumb and finger tips to
            register as a touch gesture (in normalized coordinates 0.0-1.0).
        draw_landmarks: Whether to draw hand landmarks on frames for debugging.
    """

    # MediaPipe hand landmark indices
    THUMB_TIP = 4
    INDEX_TIP = 8
    MIDDLE_TIP = 12
    RING_TIP = 16

    # MediaPipe hand connections for drawing
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),  # Index finger
        (0, 9), (9, 10), (10, 11), (11, 12),  # Middle finger
        (0, 13), (13, 14), (14, 15), (15, 16),  # Ring finger
        (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
        (5, 9), (9, 13), (13, 17),  # Palm
    ]

    # Model URL for MediaPipe Hand Landmarker
    MODEL_URL = (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    )
    MODEL_FILENAME = "hand_landmarker.task"
    # Model directory relative to project root (src/neural_nets/hand_landmarker/)
    MODEL_DIR = Path(__file__).parent.parent.parent.parent / "neural_nets" / "hand_landmarker"

    def __init__(
        self,
        touch_threshold: float = 0.06,
        release_threshold: float = 0.10,
        draw_landmarks: bool = True,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        model_path: Optional[Path] = None,
    ) -> None:
        """Initialize the hand gesture recognizer.

        Args:
            touch_threshold: Maximum normalized distance between thumb and
                finger tips to register as a touch/click (default: 0.06).
            release_threshold: Minimum normalized distance between thumb and
                finger tips to register as a release (default: 0.10).
                Must be greater than touch_threshold to create hysteresis.
            draw_landmarks: Whether to draw hand landmarks on frames for
                debugging visualization (default: False).
            min_detection_confidence: Minimum confidence for hand detection
                (default: 0.7).
            min_tracking_confidence: Minimum confidence for hand tracking
                (default: 0.5).
            model_path: Path to the hand landmarker model file. If None,
                uses MODEL_FILENAME in the same directory as this script.
                Model will be downloaded automatically if not present.

        Raises:
            RuntimeError: If model download fails or model initialization fails.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.frame_count: int = 0
        self.last_events: list[GestureType] = []
        self.touch_threshold: float = touch_threshold
        self.release_threshold: float = release_threshold
        self.draw_landmarks: bool = draw_landmarks
        self.min_detection_confidence: float = min_detection_confidence
        self.min_tracking_confidence: float = min_tracking_confidence

        # Track button press state for event detection
        self._primary_pressed: bool = False
        self._secondary_pressed: bool = False
        self._tertiary_pressed: bool = False

        # Determine model path
        if model_path is None:
            model_path = self.MODEL_DIR / self.MODEL_FILENAME

        self.model_path: Path = Path(model_path)

        # Ensure model file exists (download if necessary)
        self._ensure_model_available()

        # Initialize MediaPipe Tasks Hand Landmarker
        try:
            base_options = python.BaseOptions(
                model_asset_path=str(self.model_path)
            )
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=min_tracking_confidence,
            )
            self.landmarker = vision.HandLandmarker.create_from_options(options)

            self.logger.info(
                f"HandGestureRecognizer initialized with MediaPipe Tasks "
                f"Hand Landmarker (touch_threshold={touch_threshold}, "
                f"draw_landmarks={draw_landmarks}, "
                f"model_path={self.model_path})"
            )
        except Exception as e:
            error_msg = f"Failed to initialize MediaPipe Hand Landmarker: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _ensure_model_available(self) -> None:
        """Ensure the hand landmarker model file is available.

        Downloads the model from Google's servers if it doesn't exist locally.

        Raises:
            RuntimeError: If model download fails.
        """
        if self.model_path.exists():
            self.logger.info(f"Model file found at {self.model_path}")
            return

        self.logger.info(
            f"Model file not found at {self.model_path}. Downloading from {self.MODEL_URL}"
        )

        try:
            # Create parent directory if it doesn't exist
            self.model_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the model file
            self.logger.info("Downloading hand landmarker model...")
            urllib.request.urlretrieve(self.MODEL_URL, self.model_path)

            self.logger.info(
                f"Model downloaded successfully to {self.model_path} "
                f"(size: {self.model_path.stat().st_size} bytes)"
            )
        except Exception as e:
            error_msg = f"Failed to download model from {self.MODEL_URL}: {e}"
            self.logger.error(error_msg)
            # Clean up partial download
            if self.model_path.exists():
                self.model_path.unlink()
            raise RuntimeError(error_msg) from e

    def process_frame(self, frame: np.ndarray) -> list[GestureType]:
        """Process a single video frame and return detected gesture events.

        Analyzes the input frame to detect hand presence and generate gesture
        events based on state changes. Events are generated when buttons are
        pressed (finger touches thumb) or released (finger leaves thumb).

        Args:
            frame: Input video frame in BGR format (OpenCV standard).

        Returns:
            List of detected gesture events for this frame. An empty list
            indicates no events occurred (no state changes). Multiple events
            can occur in a single frame (e.g., one button released while
            another is pressed).

        Notes:
            - Events are generated only on state changes, not while held.
            - Frame is converted to RGB for MediaPipe processing.
            - If draw_landmarks is True, landmarks are drawn on the input frame.
            - Button state is tracked across frames to detect press/release events.
        """
        self.frame_count += 1

        if frame is None or frame.size == 0:
            self.logger.warning(
                f"Invalid frame received (count: {self.frame_count})"
            )
            return []

        self.logger.debug(
            f"Processing frame {self.frame_count}: "
            f"shape={frame.shape}, dtype={frame.dtype}"
        )

        # Convert BGR to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # Calculate timestamp in milliseconds (assuming ~30 FPS)
        timestamp_ms = self.frame_count * 33

        # Process the frame with MediaPipe Hand Landmarker
        try:
            result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception as e:
            self.logger.error(f"Hand detection failed: {e}")
            return []

        detected_events: list[GestureType] = []

        # Check if any hands were detected
        if result.hand_landmarks:
            hand_landmarks = result.hand_landmarks[0]  # Use first hand only

            # Draw landmarks if requested
            if self.draw_landmarks:
                self._draw_hand_landmarks(frame, hand_landmarks)

            # Detect button events based on state changes
            detected_events = self._detect_button_events(hand_landmarks)
        else:
            # No hand detected - release all buttons if any were pressed
            if self._primary_pressed:
                detected_events.append(GestureType.PrimaryButtonReleased)
                self._primary_pressed = False
            if self._secondary_pressed:
                detected_events.append(GestureType.SecondaryButtonReleased)
                self._secondary_pressed = False
            if self._tertiary_pressed:
                detected_events.append(GestureType.TertiaryButtonReleased)
                self._tertiary_pressed = False

        if detected_events:
            self.logger.info(
                f"Gesture events detected: {[str(evt) for evt in detected_events]}"
            )
            self.last_events = detected_events

        return detected_events

    def _draw_hand_landmarks(
        self,
        frame: np.ndarray,
        hand_landmarks: list[Any],
    ) -> None:
        """Draw hand landmarks and connections on the frame.

        Args:
            frame: BGR image to draw on (modified in-place).
            hand_landmarks: List of hand landmark objects from MediaPipe.
        """
        height, width = frame.shape[:2]

        # Draw connections (lines between landmarks)
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection
            start_landmark = hand_landmarks[start_idx]
            end_landmark = hand_landmarks[end_idx]

            # Convert normalized coordinates to pixel coordinates
            start_x = int(start_landmark.x * width)
            start_y = int(start_landmark.y * height)
            end_x = int(end_landmark.x * width)
            end_y = int(end_landmark.y * height)

            # Draw line
            cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2)

        # Draw landmark points
        for landmark in hand_landmarks:
            x = int(landmark.x * width)
            y = int(landmark.y * height)
            cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

    def _detect_button_events(self, hand_landmarks: list[Any]) -> list[GestureType]:
        """Detect button press/release events based on finger-thumb touch state changes.

        Analyzes hand landmark positions to detect which fingers are currently
        touching the thumb and generates events when the touch state changes
        compared to the previous frame. Uses Euclidean distance between thumb
        tip and finger tips to determine touch state.

        Args:
            hand_landmarks: List of MediaPipe hand landmark objects containing
                all landmark positions for a detected hand.

        Returns:
            List of gesture events generated by state changes in this frame:
                - Empty list if no state changes occurred
                - PrimaryButtonClicked/Released for index finger touch changes
                - SecondaryButtonClicked/Released for middle finger touch changes
                - TertiaryButtonClicked/Released for ring finger touch changes
                - Multiple events possible in a single frame

        Notes:
            - Events are generated only when touch state changes (not while held).
            - Uses 2D distance (x, y) in normalized coordinates.
            - Hysteresis: click at touch_threshold, release at release_threshold.
            - Updates internal button state tracking (_primary_pressed, etc.).
        """
        # Get landmark positions for thumb and relevant fingers
        thumb_tip = hand_landmarks[self.THUMB_TIP]
        index_tip = hand_landmarks[self.INDEX_TIP]
        middle_tip = hand_landmarks[self.MIDDLE_TIP]
        ring_tip = hand_landmarks[self.RING_TIP]

        # Calculate distances between thumb and each finger
        thumb_index_dist = self._calculate_distance(thumb_tip, index_tip)
        thumb_middle_dist = self._calculate_distance(thumb_tip, middle_tip)
        thumb_ring_dist = self._calculate_distance(thumb_tip, ring_tip)

        # Determine touch/release state for each finger using hysteresis
        # Click when distance < touch_threshold
        # Release when distance > release_threshold (larger threshold prevents flickering)
        primary_click = thumb_index_dist < self.touch_threshold
        primary_release = thumb_index_dist > self.release_threshold
        secondary_click = thumb_middle_dist < self.touch_threshold
        secondary_release = thumb_middle_dist > self.release_threshold
        tertiary_click = thumb_ring_dist < self.touch_threshold
        tertiary_release = thumb_ring_dist > self.release_threshold

        # Generate events based on state changes
        events: list[GestureType] = []

        # Primary button (index finger)
        if primary_click and not self._primary_pressed:
            events.append(GestureType.PrimaryButtonClicked)
            self._primary_pressed = True
            self.logger.debug(
                f"Primary button clicked (distance: {thumb_index_dist:.4f})"
            )
        elif primary_release and self._primary_pressed:
            events.append(GestureType.PrimaryButtonReleased)
            self._primary_pressed = False
            self.logger.debug(
                f"Primary button released (distance: {thumb_index_dist:.4f})"
            )

        # Secondary button (middle finger)
        if secondary_click and not self._secondary_pressed:
            events.append(GestureType.SecondaryButtonClicked)
            self._secondary_pressed = True
            self.logger.debug(
                f"Secondary button clicked (distance: {thumb_middle_dist:.4f})"
            )
        elif secondary_release and self._secondary_pressed:
            events.append(GestureType.SecondaryButtonReleased)
            self._secondary_pressed = False
            self.logger.debug(
                f"Secondary button released (distance: {thumb_middle_dist:.4f})"
            )

        # Tertiary button (ring finger)
        if tertiary_click and not self._tertiary_pressed:
            events.append(GestureType.TertiaryButtonClicked)
            self._tertiary_pressed = True
            self.logger.debug(
                f"Tertiary button clicked (distance: {thumb_ring_dist:.4f})"
            )
        elif tertiary_release and self._tertiary_pressed:
            events.append(GestureType.TertiaryButtonReleased)
            self._tertiary_pressed = False
            self.logger.debug(
                f"Tertiary button released (distance: {thumb_ring_dist:.4f})"
            )

        return events

    def _calculate_distance(
        self,
        landmark1: Any,
        landmark2: Any,
    ) -> float:
        """Calculate Euclidean distance between two hand landmarks.

        Args:
            landmark1: First landmark point with x, y, z coordinates.
            landmark2: Second landmark point with x, y, z coordinates.

        Returns:
            Euclidean distance in normalized coordinates (0.0-1.0 range).

        Notes:
            Uses 2D distance (x, y only) as z-coordinate is less reliable
            for touch detection in the camera's viewing plane.
        """
        dx = landmark1.x - landmark2.x
        dy = landmark1.y - landmark2.y
        return np.sqrt(dx * dx + dy * dy)

    def reset(self) -> None:
        """Reset the gesture recognizer state.

        Resets frame count, button state tracking, and last events.
        Does not reinitialize MediaPipe Hand Landmarker instance.
        """
        self.logger.info("Resetting gesture recognizer state")
        self.frame_count = 0
        self.last_events = []
        self._primary_pressed = False
        self._secondary_pressed = False
        self._tertiary_pressed = False

    def cleanup(self) -> None:
        """Release MediaPipe Hand Landmarker resources.

        Should be called when the gesture recognizer is no longer needed
        to properly clean up resources and prevent memory leaks.
        """
        self.logger.info("Cleaning up MediaPipe Hand Landmarker resources")
        if hasattr(self, 'landmarker'):
            self.landmarker.close()

    def get_statistics(self) -> dict[str, Any]:
        """Get current statistics about gesture recognition.

        Returns:
            Dictionary containing:
                - frame_count: Total number of frames processed
                - last_events: Most recently detected gesture events
                - primary_pressed: Whether primary button is currently pressed
                - secondary_pressed: Whether secondary button is currently pressed
                - tertiary_pressed: Whether tertiary button is currently pressed
                - status: Current status (active/idle)
                - touch_threshold: Current touch detection threshold
                - release_threshold: Current release detection threshold
        """
        return {
            "frame_count": self.frame_count,
            "last_events": [str(evt) for evt in self.last_events],
            "primary_pressed": self._primary_pressed,
            "secondary_pressed": self._secondary_pressed,
            "tertiary_pressed": self._tertiary_pressed,
            "status": "active" if self.frame_count > 0 else "idle",
            "touch_threshold": self.touch_threshold,
            "release_threshold": self.release_threshold,
        }
