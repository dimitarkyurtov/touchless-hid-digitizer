#!/usr/bin/env python3
"""HID Digitizer Main Service.

This is the main entry point for the HID digitizer device service running
on the Raspberry Pi. It integrates the HID controller and serial listener
to receive commands from the host application and control the HID digitizer.

The service runs as a system daemon, typically started by systemd. It handles
the complete lifecycle of:
    1. Opening the HID gadget device (/dev/hidg0)
    2. Opening the serial port (/dev/ttyGS0)
    3. Listening for commands from the host
    4. Parsing commands using the common protocol
    5. Executing HID actions (move cursor, click buttons)
    6. Sending responses back to the host
    7. Graceful shutdown on signals (SIGINT, SIGTERM)

The service implements error recovery and will attempt to continue operation
even if individual commands fail. It logs all activities for debugging and
monitoring.

Example:
    Run as a standalone service::

        sudo python3 main.py

    Or install as a systemd service (see setup documentation).

Signal Handling:
    SIGINT (Ctrl+C): Graceful shutdown
    SIGTERM: Graceful shutdown (used by systemd)
"""

import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional

import cv2

# Add parent directory to path to import common module
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.camera import Camera
from common.protocol import (
    CMD_CLICK,
    CMD_GESTURE_START,
    CMD_GESTURE_STOP,
    CMD_MOVE,
    CMD_RELEASE,
    CommandFormatter,
    CommandParser,
    InvalidButtonError,
    InvalidCoordinateError,
    ProtocolError,
)
from config import (
    BUTTON_BARREL,
    BUTTON_TIP_SWITCH,
    LOG_FILE,
    LOG_LEVEL,
    LOG_TO_CONSOLE,
    LOG_TO_FILE,
    SERVICE_NAME,
)
from gesture_types import GestureType
from hand_gesture_recognizer import HandGestureRecognizer
from hid_controller import HIDController
from serial_listener import SerialListener


class HIDDigitizerService:
    """Main HID Digitizer service controller.

    Coordinates serial communication and HID report generation. Manages
    the lifecycle of both the HID controller and serial listener components.

    This service acts as the command processor, receiving commands from the
    serial port, parsing them, and translating them into HID actions.

    Attributes:
        logger (logging.Logger): Service logger instance.
        hid (HIDController): HID report controller.
        serial (SerialListener): Serial command listener.
        running (bool): Flag indicating if service is running.
    """

    def __init__(self) -> None:
        """Initialize service components and signal handlers.

        Sets up logging, creates HID controller and serial listener instances,
        and registers signal handlers for graceful shutdown.
        """
        self.setup_logging()
        self.logger: logging.Logger = logging.getLogger(__name__)

        self.hid: HIDController = HIDController()
        self.serial: SerialListener = SerialListener()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.running: bool = False

        # Hand gesture recognition state
        self._gesture_recognizer: Optional[HandGestureRecognizer] = None
        self._gesture_camera: Optional[Camera] = None

    def setup_logging(self) -> None:
        """Configure logging based on config settings.

        Sets up console and/or file logging handlers according to LOG_TO_CONSOLE
        and LOG_TO_FILE configuration. Falls back gracefully if file logging
        cannot be initialized.
        """
        handlers = []

        # Console handler for stdout
        if LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
            handlers.append(console_handler)

        # File handler for persistent logs
        if LOG_TO_FILE:
            try:
                file_handler = logging.FileHandler(LOG_FILE)
                file_handler.setFormatter(
                    logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    )
                )
                handlers.append(file_handler)
            except (IOError, PermissionError) as e:
                print(f"Warning: Could not create log file {LOG_FILE}: {e}",
                      file=sys.stderr)

        # Configure root logger with handlers
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL),
            handlers=handlers,
        )

    def _start_gesture_recognition(self) -> None:
        """Start hand gesture recognition using the Pi camera."""
        if self._gesture_camera is not None:
            self.logger.warning("Gesture recognition already running")
            return

        try:
            self._gesture_recognizer = HandGestureRecognizer()
            self.logger.info("Hand gesture recognizer initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize gesture recognizer: {e}")
            raise

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.logger.error("Failed to open camera for gesture recognition")
            self._gesture_recognizer = None
            raise RuntimeError("Failed to open camera")

        self._gesture_camera = Camera(cap, 30)
        self._gesture_camera.register_callback(self._process_gesture_frame)
        self._gesture_camera.start()
        self.logger.info("Gesture recognition started")

    def _stop_gesture_recognition(self) -> None:
        """Stop hand gesture recognition and release resources."""
        if self._gesture_camera is not None:
            self._gesture_camera.stop()
            self._gesture_camera = None
            self.logger.info("Gesture camera stopped")

        if self._gesture_recognizer is not None:
            self._gesture_recognizer.cleanup()
            self._gesture_recognizer = None
            self.logger.info("Gesture recognizer cleaned up")

        self.logger.info("Gesture recognition stopped")

    def _process_gesture_frame(self, frame) -> None:
        """Process a camera frame for gesture recognition.

        Processes the frame to detect hand gestures and sends corresponding
        HID reports for button events. Button state is managed by setting or
        clearing bits in the current button mask, then sending a report at
        the current cursor position.

        Args:
            frame: Captured video frame from the Pi camera.
        """
        if self._gesture_recognizer is None:
            return

        events = self._gesture_recognizer.process_frame(frame)
        for event in events:
            self.logger.info(f"Gesture event detected: {event}")

            # Handle button click/release events
            if event == GestureType.PrimaryButtonClicked:
                # Set left button bit (BUTTON_TIP_SWITCH)
                self.hid.current_buttons |= BUTTON_TIP_SWITCH
                self.hid.send_report(
                    self.hid.current_x,
                    self.hid.current_y,
                    self.hid.current_buttons,
                    in_range=True
                )
                self.logger.info(f"Primary button pressed at ({self.hid.current_x}, {self.hid.current_y})")

            elif event == GestureType.PrimaryButtonReleased:
                # Clear left button bit
                self.hid.current_buttons &= ~BUTTON_TIP_SWITCH
                self.hid.send_report(
                    self.hid.current_x,
                    self.hid.current_y,
                    self.hid.current_buttons,
                    in_range=True
                )
                self.logger.info(f"Primary button released at ({self.hid.current_x}, {self.hid.current_y})")

            elif event == GestureType.SecondaryButtonClicked:
                # Set right button bit (BUTTON_BARREL)
                self.hid.current_buttons |= BUTTON_BARREL
                self.hid.send_report(
                    self.hid.current_x,
                    self.hid.current_y,
                    self.hid.current_buttons,
                    in_range=True
                )
                self.logger.info(f"Secondary button pressed at ({self.hid.current_x}, {self.hid.current_y})")

            elif event == GestureType.SecondaryButtonReleased:
                # Clear right button bit
                self.hid.current_buttons &= ~BUTTON_BARREL
                self.hid.send_report(
                    self.hid.current_x,
                    self.hid.current_y,
                    self.hid.current_buttons,
                    in_range=True
                )
                self.logger.info(f"Secondary button released at ({self.hid.current_x}, {self.hid.current_y})")

            elif event == GestureType.TertiaryButtonClicked:
                self.hid.play_pause()
                self.logger.info("Tertiary button -> Play/Pause media key")

            elif event == GestureType.ThumbsUp:
                self.hid.next_track()
                self.logger.info("ThumbsUp -> Next Track media key")

            elif event == GestureType.ThumbsDown:
                self.hid.prev_track()
                self.logger.info("ThumbsDown -> Previous Track media key")

            elif event == GestureType.TertiaryButtonReleased:
                # Media keys use press-and-release, no hold needed
                pass

            else:
                self.logger.info(f"Unhandled gesture event: {event}")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals (SIGINT, SIGTERM).

        Args:
            signum: Signal number that was received.
            frame: Current stack frame (unused).

        Note:
            This method exits the process after shutdown. It does not return.
        """
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)

    def handle_command(self, command_str: str) -> None:
        """Process received command from serial port.

        Parses the command string, executes the corresponding HID action,
        and sends a response back to the host. Handles all protocol errors
        gracefully, logging issues and responding with error messages.

        Args:
            command_str: Command string from host (e.g., "MOVE 100 200").

        Note:
            This method never raises exceptions - all errors are caught,
            logged, and reported back to the host via serial response.
            This ensures the service continues running even if individual
            commands fail.
        """
        try:
            # Parse command using common protocol parser
            cmd_type, params = CommandParser.parse(command_str)

            # Execute command based on type
            if cmd_type == CMD_MOVE:
                x = params["x"]
                y = params["y"]
                self.logger.info(f"Executing MOVE to ({x}, {y})")
                self.hid.move(x, y)
                self.serial.send_response(CommandFormatter.format_response(True))

            elif cmd_type == CMD_CLICK:
                button = params["button"]
                self.logger.info(f"Executing CLICK {button}")
                self.hid.click(button)
                self.serial.send_response(CommandFormatter.format_response(True))

            elif cmd_type == CMD_RELEASE:
                self.logger.info("Executing RELEASE")
                self.hid.release()
                self.serial.send_response(CommandFormatter.format_response(True))

            elif cmd_type == CMD_GESTURE_START:
                self.logger.info("Received GESTURE_START command")
                try:
                    self._start_gesture_recognition()
                    self.serial.send_response(CommandFormatter.format_response(True))
                except Exception as e:
                    error_msg = f"Failed to start gesture recognition: {e}"
                    self.logger.error(error_msg)
                    self.serial.send_response(
                        CommandFormatter.format_response(False, error_msg)
                    )

            elif cmd_type == CMD_GESTURE_STOP:
                self.logger.info("Received GESTURE_STOP command")
                self._stop_gesture_recognition()
                self.serial.send_response(CommandFormatter.format_response(True))

            else:
                # Should not happen if parser is correct
                error_msg = f"Unknown command type: {cmd_type}"
                self.logger.error(error_msg)
                self.serial.send_response(
                    CommandFormatter.format_response(False, error_msg)
                )

        except InvalidCoordinateError as e:
            self.logger.warning(f"Invalid coordinates: {e}")
            self.serial.send_response(CommandFormatter.format_response(False, str(e)))

        except InvalidButtonError as e:
            self.logger.warning(f"Invalid button: {e}")
            self.serial.send_response(CommandFormatter.format_response(False, str(e)))

        except ProtocolError as e:
            self.logger.warning(f"Protocol error: {e}")
            self.serial.send_response(CommandFormatter.format_response(False, str(e)))

        except Exception as e:
            # Catch-all for unexpected errors
            self.logger.error(f"Error handling command: {e}", exc_info=True)
            self.serial.send_response(
                CommandFormatter.format_response(False, "Internal error")
            )

    def run(self) -> None:
        """Start the service and enter main event loop.

        Opens HID and serial devices, initializes the digitizer, and starts
        listening for commands. This method blocks until the service is
        stopped by a signal or fatal error.

        The service lifecycle:
            1. Open HID device
            2. Open serial port
            3. Reset digitizer to safe state
            4. Listen for commands (blocking)
            5. Shutdown on interrupt or error

        Note:
            This method does not return under normal operation. It runs
            until interrupted by a signal or fatal error, then exits
            the process.
        """
        try:
            self.logger.info(f"Starting {SERVICE_NAME} service...")
            self.logger.info(f"Protocol version: {CommandParser.__module__}")

            # Open devices
            self.hid.open()
            self.serial.open()

            # Initialize digitizer to origin with no buttons pressed
            self.logger.info("Initializing digitizer...")
            self.hid.reset()

            self.logger.info("Service ready, listening for commands...")
            self.running = True

            # Start listening for commands (blocking call)
            self.serial.listen(self.handle_command)

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
            self.shutdown()

        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            self.shutdown()
            sys.exit(1)

    def shutdown(self) -> None:
        """Cleanup resources and shutdown service gracefully.

        Stops the serial listener, resets the digitizer to a safe state,
        and closes all devices. Safe to call multiple times.

        This method suppresses exceptions during cleanup to ensure shutdown
        completes even if individual operations fail.
        """
        if not self.running:
            return

        self.logger.info("Shutting down service...")
        self.running = False

        # Stop gesture recognition if running
        try:
            self._stop_gesture_recognition()
        except Exception as e:
            self.logger.error(f"Error stopping gesture recognition: {e}")

        # Stop serial listener
        self.serial.stop()

        # Reset digitizer to safe state (cursor at origin, no buttons)
        try:
            if self.hid.is_open():
                self.hid.reset()
        except Exception as e:
            self.logger.error(f"Error resetting HID device: {e}")

        # Close devices
        self.serial.close()
        self.hid.close()

        self.logger.info("Service stopped")


def main() -> None:
    """Main entry point for the HID digitizer service.

    Checks for root privileges (required for /dev/hidg0 access),
    creates the service instance, and starts it.

    Note:
        This function does not return under normal operation.
        It runs until the service is stopped by a signal.
    """
    # Check if running as root (required for /dev/hidg0 access)
    if os.geteuid() != 0:
        print("Warning: This service typically requires root privileges",
              file=sys.stderr)
        print("If you encounter permission errors, try running with sudo",
              file=sys.stderr)

    # Create and run service
    service = HIDDigitizerService()
    service.run()


if __name__ == "__main__":
    main()
