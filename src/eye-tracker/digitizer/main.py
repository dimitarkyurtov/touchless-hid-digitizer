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

# Add parent directory to path to import common module
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.protocol import (
    CMD_CLICK,
    CMD_MOVE,
    CMD_RELEASE,
    CommandFormatter,
    CommandParser,
    InvalidButtonError,
    InvalidCoordinateError,
    ProtocolError,
)
from config import (
    LOG_FILE,
    LOG_LEVEL,
    LOG_TO_CONSOLE,
    LOG_TO_FILE,
    SERVICE_NAME,
)
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
