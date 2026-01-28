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
from collections import deque
from pathlib import Path
from typing import Any, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
from skimage.transform import resize

from common.gesture_types import GestureType

# Force TensorFlow to use CPU only (for Raspberry Pi compatibility)
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF info messages

# Optional TensorFlow import for LSTM gesture recognition
try:
    import tensorflow as tf
    # Disable GPU devices to force CPU inference
    tf.config.set_visible_devices([], 'GPU')
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    tf = None


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
    MODEL_DIR = Path(__file__).parent.parent.parent / "neural_nets" / "hand_landmarker"

    # LSTM model configuration for continuous gestures (ThumbsUp, ThumbsDown)
    LSTM_MODEL_DIR = Path(__file__).parent.parent.parent / "neural_nets" / "hand_gesture_recongnizer"
    LSTM_MODEL_FILENAME = "hand_gesture_recognizer_model.h5"
    LSTM_FRAMES = 10  # Number of frames required for LSTM sequence
    LSTM_ROWS = 120  # LSTM model input height
    LSTM_COLS = 120  # LSTM model input width
    LSTM_CHANNELS = 3  # RGB channels
    # Only gestures we care about from the LSTM model (indices from training)
    LSTM_GESTURE_LABELS = {
        3: GestureType.ThumbsDown,
        4: GestureType.ThumbsUp,
    }
    # Cooldown period (in frames) to avoid rapid repeated detections
    LSTM_COOLDOWN_FRAMES = 20

    def __init__(
        self,
        touch_threshold: float = 0.06,
        release_threshold: float = 0.10,
        draw_landmarks: bool = True,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        model_path: Optional[Path] = None,
        lstm_model_path: Optional[Path] = None,
        lstm_confidence_threshold: float = 0.85,
        enable_continuous_gestures: bool = True,
        lstm_frame_skip: int = 3,
    ) -> None:
        """Initialize the hand gesture recognizer.

        Args:
            touch_threshold: Maximum normalized distance between thumb and
                finger tips to register as a touch/click (default: 0.06).
            release_threshold: Minimum normalized distance between thumb and
                finger tips to register as a release (default: 0.10).
                Must be greater than touch_threshold to create hysteresis.
            draw_landmarks: Whether to draw hand landmarks on frames for
                debugging visualization (default: True).
            min_detection_confidence: Minimum confidence for hand detection
                (default: 0.7).
            min_tracking_confidence: Minimum confidence for hand tracking
                (default: 0.5).
            model_path: Path to the hand landmarker model file. If None,
                uses MODEL_FILENAME in the same directory as this script.
                Model will be downloaded automatically if not present.
            lstm_model_path: Path to the LSTM gesture recognition model file.
                If None, uses LSTM_MODEL_FILENAME in LSTM_MODEL_DIR.
                Set to False to disable LSTM gesture recognition entirely.
            lstm_confidence_threshold: Minimum confidence for LSTM gesture
                detection (default: 0.7). Higher values reduce false positives.
            enable_continuous_gestures: Enable LSTM-based continuous gesture
                recognition (ThumbsUp, ThumbsDown). Requires TensorFlow
                (default: True).
            lstm_frame_skip: Process every Nth frame for LSTM inference to
                reduce computational load (default: 3).

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
        self.lstm_confidence_threshold: float = lstm_confidence_threshold
        self.lstm_frame_skip: int = lstm_frame_skip

        # Track button press state for event detection
        self._primary_pressed: bool = False
        self._secondary_pressed: bool = False
        self._tertiary_pressed: bool = False

        # LSTM gesture recognition state
        self.enable_continuous_gestures: bool = enable_continuous_gestures
        self.lstm_model: Optional[Any] = None
        self._lstm_frame_buffer: deque = deque(maxlen=self.LSTM_FRAMES)
        self._lstm_frame_counter: int = 0
        self._lstm_cooldown_counter: dict[GestureType, int] = {
            GestureType.ThumbsUp: 0,
            GestureType.ThumbsDown: 0,
        }

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

        # Initialize LSTM model for continuous gestures
        if enable_continuous_gestures and lstm_model_path is not False:
            self._initialize_lstm_model(lstm_model_path)
        else:
            self.logger.info("LSTM continuous gesture recognition disabled")
            self.enable_continuous_gestures = False

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

    def _initialize_lstm_model(self, lstm_model_path: Optional[Path]) -> None:
        """Initialize the LSTM model for continuous gesture recognition.

        Args:
            lstm_model_path: Path to the LSTM model file. If None, uses
                LSTM_MODEL_FILENAME in LSTM_MODEL_DIR.

        Notes:
            If TensorFlow is not available or model loading fails, disables
            continuous gesture recognition and logs a warning instead of
            raising an error.
        """
        # Check if TensorFlow is available
        if not TENSORFLOW_AVAILABLE:
            self.logger.warning(
                "TensorFlow not available. LSTM continuous gesture "
                "recognition disabled. Install tensorflow to enable: "
                "pip install tensorflow"
            )
            self.enable_continuous_gestures = False
            return

        # Determine LSTM model path
        if lstm_model_path is None:
            lstm_model_path = self.LSTM_MODEL_DIR / self.LSTM_MODEL_FILENAME

        lstm_model_path = Path(lstm_model_path)

        # Check if model exists
        if not lstm_model_path.exists():
            self.logger.warning(
                f"LSTM model not found at {lstm_model_path}. "
                f"Continuous gesture recognition disabled. "
                f"Place the model file at this location to enable ThumbsUp/"
                f"ThumbsDown gestures."
            )
            self.enable_continuous_gestures = False
            return

        # Load the LSTM model
        try:
            self.logger.info(f"Loading LSTM model from {lstm_model_path}")
            self.lstm_model = tf.keras.models.load_model(
                str(lstm_model_path),
                compile=False,  # Skip compilation for inference-only usage
            )
            self.logger.info(
                f"LSTM model loaded successfully. Continuous gesture "
                f"recognition enabled (confidence_threshold="
                f"{self.lstm_confidence_threshold}, frame_skip="
                f"{self.lstm_frame_skip})"
            )
        except Exception as e:
            self.logger.warning(
                f"Failed to load LSTM model from {lstm_model_path}: {e}. "
                f"Continuous gesture recognition disabled."
            )
            self.enable_continuous_gestures = False
            self.lstm_model = None

    def process_frame(self, frame: np.ndarray) -> list[GestureType]:
        """Process a single video frame and return detected gesture events.

        Analyzes the input frame to detect hand presence and generate gesture
        events based on state changes. Events are generated when buttons are
        pressed (finger touches thumb) or released (finger leaves thumb).

        Also processes frames for LSTM-based continuous gesture recognition
        (ThumbsUp, ThumbsDown) if enabled.

        Args:
            frame: Input video frame in BGR format (OpenCV standard).

        Returns:
            List of detected gesture events for this frame. An empty list
            indicates no events occurred (no state changes). Multiple events
            can occur in a single frame (e.g., one button released while
            another is pressed, or finger-touch and continuous gestures).

        Notes:
            - Events are generated only on state changes, not while held.
            - Frame is converted to RGB for MediaPipe processing.
            - If draw_landmarks is True, landmarks are drawn on the input frame.
            - Button state is tracked across frames to detect press/release events.
            - LSTM gestures are detected from sequences of frames.
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

        # Process LSTM continuous gestures if enabled
        lstm_events: list[GestureType] = []
        if self.enable_continuous_gestures and self.lstm_model is not None:
            # Add frame to LSTM buffer at intervals
            self._lstm_frame_counter += 1
            if self._lstm_frame_counter % self.lstm_frame_skip == 0:
                try:
                    preprocessed_frame = self._preprocess_frame_for_lstm(frame)
                    self._lstm_frame_buffer.append(preprocessed_frame)
                except Exception as e:
                    self.logger.debug(f"LSTM frame preprocessing failed: {e}")

            # Detect continuous gestures when buffer is full
            if len(self._lstm_frame_buffer) == self.LSTM_FRAMES:
                try:
                    lstm_events = self._detect_continuous_gestures()
                except Exception as e:
                    self.logger.debug(f"LSTM gesture detection failed: {e}")

        # Merge all detected events
        all_events = detected_events + lstm_events

        if all_events:
            self.logger.info(
                f"Gesture events detected: {[str(evt) for evt in all_events]}"
            )
            self.last_events = all_events

        return all_events

    def _preprocess_frame_for_lstm(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess a frame for LSTM model input.

        Applies the same preprocessing pipeline used during model training:
        1. Convert to float32
        2. Convert BGR to RGB
        3. Crop center square and resize to (LSTM_ROWS, LSTM_COLS)
        4. Normalize to [0, 1]

        Args:
            frame: Input video frame in BGR format (height, width, 3).

        Returns:
            Preprocessed frame in RGB format with shape (LSTM_ROWS, LSTM_COLS, 3)
            and values normalized to [0, 1].

        Raises:
            ValueError: If frame is invalid or has incorrect shape.
        """
        if frame is None or frame.size == 0:
            raise ValueError("Invalid frame for LSTM preprocessing")

        # Convert to float32 (like training)
        frame_float = frame.astype(np.float32)

        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame_float, cv2.COLOR_BGR2RGB)

        # Crop center square and resize
        h, w = frame_rgb.shape[:2]
        if h != w:
            size = min(h, w)
            start_h = (h - size) // 2
            start_w = (w - size) // 2
            frame_rgb = frame_rgb[start_h:start_h+size, start_w:start_w+size]

        # Resize to model input dimensions
        frame_resized = resize(
            frame_rgb,
            (self.LSTM_ROWS, self.LSTM_COLS),
            anti_aliasing=True
        )

        # Normalize to [0, 1]
        frame_normalized = frame_resized / 255.0 if frame_resized.max() > 1.0 else frame_resized

        return frame_normalized

    def _detect_continuous_gestures(self) -> list[GestureType]:
        """Detect continuous gestures (ThumbsUp, ThumbsDown) using LSTM model.

        Prepares a sequence of preprocessed frames and runs LSTM inference
        to detect continuous hand gestures. Uses cooldown mechanism to avoid
        rapid repeated detections.

        Returns:
            List of detected continuous gesture events. Empty if no gestures
            detected or if gestures are in cooldown period.

        Notes:
            - Requires exactly LSTM_FRAMES frames in the buffer
            - Only returns gestures with confidence > lstm_confidence_threshold
            - Clears half the buffer after prediction for continuity
            - Uses cooldown to prevent rapid repeated detections
            - Only detects ThumbsUp and ThumbsDown (indices 3 and 4 from model)
        """
        if len(self._lstm_frame_buffer) != self.LSTM_FRAMES:
            return []

        # Prepare sequence for model input
        sequence = np.zeros(
            (1, self.LSTM_FRAMES, self.LSTM_ROWS, self.LSTM_COLS, self.LSTM_CHANNELS),
            dtype=np.float32
        )
        for i, frame in enumerate(self._lstm_frame_buffer):
            sequence[0, i] = frame

        # Run inference
        predictions = self.lstm_model.predict(sequence, verbose=0)
        predicted_class = int(np.argmax(predictions[0]))
        confidence = float(predictions[0][predicted_class])

        # Log confidence for ThumbsUp and ThumbsDown on each inference
        thumbs_down_conf = float(predictions[0][3])  # Index 3 = ThumbsDown
        thumbs_up_conf = float(predictions[0][4])    # Index 4 = ThumbsUp
        self.logger.info(
            f"LSTM confidence - ThumbsDown: {thumbs_down_conf:.2%}, "
            f"ThumbsUp: {thumbs_up_conf:.2%} "
            f"(predicted: class {predicted_class} @ {confidence:.2%})"
        )

        # Update cooldown counters
        for gesture_type in self._lstm_cooldown_counter:
            if self._lstm_cooldown_counter[gesture_type] > 0:
                self._lstm_cooldown_counter[gesture_type] -= 1

        # Check if predicted gesture is one we care about
        detected_events: list[GestureType] = []
        if predicted_class in self.LSTM_GESTURE_LABELS:
            gesture_type = self.LSTM_GESTURE_LABELS[predicted_class]

            # Check confidence threshold and cooldown
            if confidence >= self.lstm_confidence_threshold:
                if self._lstm_cooldown_counter[gesture_type] == 0:
                    detected_events.append(gesture_type)
                    self._lstm_cooldown_counter[gesture_type] = self.LSTM_COOLDOWN_FRAMES
                    self.logger.info(
                        f"LSTM gesture detected: {gesture_type} "
                        f"(confidence: {confidence:.2%})"
                    )
                else:
                    self.logger.debug(
                        f"LSTM gesture {gesture_type} in cooldown "
                        f"({self._lstm_cooldown_counter[gesture_type]} frames)"
                    )

        # Clear half the buffer for continuity (like in example code)
        for _ in range(self.LSTM_FRAMES // 2):
            if self._lstm_frame_buffer:
                self._lstm_frame_buffer.popleft()

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

        Resets frame count, button state tracking, last events, and LSTM buffers.
        Does not reinitialize MediaPipe Hand Landmarker or LSTM model instances.
        """
        self.logger.info("Resetting gesture recognizer state")
        self.frame_count = 0
        self.last_events = []
        self._primary_pressed = False
        self._secondary_pressed = False
        self._tertiary_pressed = False

        # Reset LSTM state
        self._lstm_frame_buffer.clear()
        self._lstm_frame_counter = 0
        for gesture_type in self._lstm_cooldown_counter:
            self._lstm_cooldown_counter[gesture_type] = 0

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
                - lstm_enabled: Whether LSTM continuous gesture recognition is enabled
                - lstm_buffer_size: Current number of frames in LSTM buffer
                - lstm_cooldowns: Cooldown status for continuous gestures
        """
        stats = {
            "frame_count": self.frame_count,
            "last_events": [str(evt) for evt in self.last_events],
            "primary_pressed": self._primary_pressed,
            "secondary_pressed": self._secondary_pressed,
            "tertiary_pressed": self._tertiary_pressed,
            "status": "active" if self.frame_count > 0 else "idle",
            "touch_threshold": self.touch_threshold,
            "release_threshold": self.release_threshold,
            "lstm_enabled": self.enable_continuous_gestures,
        }

        # Add LSTM statistics if enabled
        if self.enable_continuous_gestures:
            stats["lstm_buffer_size"] = len(self._lstm_frame_buffer)
            stats["lstm_cooldowns"] = {
                str(gesture): cooldown
                for gesture, cooldown in self._lstm_cooldown_counter.items()
            }

        return stats
