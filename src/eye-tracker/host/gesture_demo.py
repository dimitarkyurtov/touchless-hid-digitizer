#!/usr/bin/env python3
import logging
import sys
import time
from pathlib import Path
from typing import NoReturn, Optional

import cv2
import numpy as np

# Add parent directory to path to import common module
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.gesture_types import GestureType
from config import GESTURE_CAMERA_INDEX
from hand_gesture_recognizer import HandGestureRecognizer

# Default to gesture camera index from config, can be overridden via command line
CAMERA_INDEX: int = GESTURE_CAMERA_INDEX
WINDOW_NAME: str = "Hand Gesture Recognition Demo"
DISPLAY_WIDTH: int = 640
DISPLAY_HEIGHT: int = 480
FPS_UPDATE_INTERVAL: float = 1.0  # Update FPS display every second

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.7
FONT_THICKNESS = 2
TEXT_COLOR = (0, 255, 0)  # Green
BG_COLOR = (0, 0, 0)  # Black
TEXT_PADDING = 10

events_str = "None"


class GestureDemo:
    def __init__(self, camera_index: int = CAMERA_INDEX) -> None:
        """Initialize the gesture demo application.

        Args:
            camera_index: Index of the camera device to use. Default is 0
                (typically the built-in webcam). Use 1, 2, etc. for external
                USB cameras.

        Raises:
            RuntimeError: If camera initialization fails.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.camera_index: int = camera_index
        self.camera: Optional[cv2.VideoCapture] = None
        self.recognizer: HandGestureRecognizer = HandGestureRecognizer()
        self.running: bool = False
        self.frame_count: int = 0
        self.fps: float = 0.0
        self.last_fps_update: float = 0.0
        self.fps_frame_count: int = 0

        self.logger.info(f"Gesture demo initialized with camera {camera_index}")

    def initialize_camera(self) -> None:
        """Open and configure the camera device.

        Initializes the camera, sets resolution, and verifies successful
        connection. Raises an exception if camera access fails.

        Raises:
            RuntimeError: If camera cannot be opened or configured.
        """
        self.logger.info(f"Opening camera device {self.camera_index}...")
        self.camera = cv2.VideoCapture(self.camera_index)

        if not self.camera.isOpened():
            error_msg = (
                f"Failed to open camera {self.camera_index}. "
                f"Please check:\n"
                f"  1. Camera is connected and not in use by another application\n"
                f"  2. Camera permissions are granted\n"
                f"  3. Camera index is correct (try 0, 1, 2, ...)"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, DISPLAY_WIDTH)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, DISPLAY_HEIGHT)

        ret, test_frame = self.camera.read()
        if not ret or test_frame is None:
            error_msg = "Camera opened but failed to capture frames"
            self.logger.error(error_msg)
            self.camera.release()
            raise RuntimeError(error_msg)

        actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.logger.info(
            f"Camera initialized successfully: {actual_width}x{actual_height}"
        )

    def draw_text_with_background(
        self,
        frame: np.ndarray,
        text: str,
        position: tuple[int, int],
        font_scale: float = FONT_SCALE,
        thickness: int = FONT_THICKNESS,
    ) -> None:
        """Draw text with a background rectangle for better visibility.

        Args:
            frame: Image to draw on (modified in-place).
            text: Text string to display.
            position: (x, y) position for bottom-left corner of text.
            font_scale: Font size scaling factor.
            thickness: Text thickness in pixels.
        """
        # Get text size
        (text_width, text_height), baseline = cv2.getTextSize(
            text, FONT, font_scale, thickness
        )

        # Calculate background rectangle coordinates
        x, y = position
        bg_top_left = (x - TEXT_PADDING, y - text_height - TEXT_PADDING)
        bg_bottom_right = (x + text_width + TEXT_PADDING, y + baseline + TEXT_PADDING)

        # Draw background rectangle
        cv2.rectangle(frame, bg_top_left, bg_bottom_right, BG_COLOR, -1)

        # Draw text
        cv2.putText(frame, text, position, FONT, font_scale, TEXT_COLOR, thickness)

    def update_fps(self) -> None:
        """Update FPS calculation.

        Calculates frames per second based on frame count and elapsed time.
        Updates the FPS display value at regular intervals.
        """
        current_time = time.time()
        self.fps_frame_count += 1

        # Update FPS every second
        if current_time - self.last_fps_update >= FPS_UPDATE_INTERVAL:
            elapsed = current_time - self.last_fps_update
            self.fps = self.fps_frame_count / elapsed
            self.fps_frame_count = 0
            self.last_fps_update = current_time

    def process_and_display_frame(self, frame: np.ndarray) -> None:
        """Process frame for gesture recognition and add display overlays.

        Args:
            frame: BGR image from camera (modified in-place with overlays).
        """
        # Recognize gestures (returns list of events)
        events = self.recognizer.process_frame(frame)

        # Update FPS
        self.update_fps()
        self.frame_count += 1

        global events_str

        # Draw events label (top-left)
        if events:
            events_str = ", ".join(str(e) for e in events)
        # else:
        #     events_str = "None"
        gesture_text = f"Events: {events_str}"
        self.draw_text_with_background(frame, gesture_text, (20, 40))

        # Draw FPS (top-right)
        fps_text = f"FPS: {self.fps:.1f}"
        fps_width = cv2.getTextSize(fps_text, FONT, FONT_SCALE, FONT_THICKNESS)[0][0]
        fps_x = frame.shape[1] - fps_width - 20 - TEXT_PADDING
        self.draw_text_with_background(frame, fps_text, (fps_x, 40))

        # Draw frame count (bottom-left)
        frame_text = f"Frames: {self.frame_count}"
        frame_y = frame.shape[0] - 20
        self.draw_text_with_background(frame, frame_text, (20, frame_y))

        # Draw instructions (bottom-center)
        instructions = "Press 'q' to quit"
        inst_width = cv2.getTextSize(
            instructions, FONT, FONT_SCALE * 0.8, FONT_THICKNESS - 1
        )[0][0]
        inst_x = (frame.shape[1] - inst_width) // 2
        self.draw_text_with_background(
            frame,
            instructions,
            (inst_x, frame_y),
            font_scale=FONT_SCALE * 0.8,
            thickness=FONT_THICKNESS - 1,
        )

    def run(self) -> None:
        """Start the demo application main loop.

        Captures frames from the camera, processes them for gesture recognition,
        and displays the results in a window. Runs until the user presses 'q'
        or closes the window.

        This method blocks until the demo is stopped.

        Raises:
            RuntimeError: If camera is not initialized.
        """
        if self.camera is None:
            raise RuntimeError("Camera not initialized. Call initialize_camera() first.")

        self.logger.info("Starting gesture demo main loop...")
        self.logger.info(f"Display window: {WINDOW_NAME}")
        self.logger.info("Press 'q' to quit")

        self.running = True
        self.last_fps_update = time.time()

        # Create display window
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

        try:
            while self.running:
                # Capture frame
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    self.logger.warning("Failed to capture frame")
                    continue

                # Process and display frame
                self.process_and_display_frame(frame)

                # Show frame
                cv2.imshow(WINDOW_NAME, frame)

                # Check for quit command (q key or window close)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.logger.info("User requested quit (q key)")
                    self.running = False
                elif cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    self.logger.info("Window closed by user")
                    self.running = False

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt (Ctrl+C)")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
            raise
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Release camera and close all windows.

        Ensures proper cleanup of resources even if errors occurred during
        execution. Safe to call multiple times.
        """
        self.logger.info("Cleaning up resources...")

        if self.camera is not None:
            self.camera.release()
            self.logger.info("Camera released")

        cv2.destroyAllWindows()
        self.logger.info("Display windows closed")

        # Print final statistics
        stats = self.recognizer.get_statistics()
        self.logger.info(f"Final statistics: {stats}")
        self.logger.info("Demo shutdown complete")


def setup_logging() -> None:
    """Configure logging for the demo application.

    Sets up console logging with timestamps and appropriate formatting
    for demo output.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> NoReturn:
    """Main entry point for the gesture demo application.

    Initializes logging, creates the demo instance, and runs the main loop.
    Handles errors gracefully and ensures proper cleanup.

    Exit Codes:
        0: Normal exit (user quit with 'q')
        1: Error occurred (camera failure, etc.)
    """
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Hand Gesture Recognition Demo")
    logger.info("Touchless HID Digitizer Project")
    logger.info("=" * 60)

    try:
        demo = GestureDemo()
        demo.initialize_camera()
        demo.run()
        logger.info("Demo completed successfully")
        sys.exit(0)

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
