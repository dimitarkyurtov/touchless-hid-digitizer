"""Serial Client for HID Digitizer Host.

This module handles serial communication with the HID digitizer device from
the host application. It provides a high-level interface for sending commands
and receiving responses over USB CDC ACM serial.

The serial client wraps the common protocol formatter and handles the details
of serial port communication, including port discovery, connection management,
and error handling.

Example:
    Send commands to the digitizer::

        client = SerialClient()
        if client.connect("/dev/ttyACM0"):
            success, error = client.move(16384, 8192)
            if success:
                print("Moved successfully")
            client.disconnect()

    Or use as a context manager::

        with SerialClient() as client:
            client.connect("/dev/ttyACM0")
            client.click("left")
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import serial
import serial.tools.list_ports

# Add parent directory to path to import common module
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.protocol import (
    SERIAL_BAUDRATE,
    CommandFormatter,
    format_command_for_send,
    parse_response,
)
from config import SERIAL_TIMEOUT


class SerialClient:
    """Serial communication client for HID digitizer.

    Provides a high-level interface for communicating with the HID digitizer
    device over serial. Handles port enumeration, connection management,
    command formatting, and response parsing.

    This class implements the context manager protocol for automatic
    resource management.

    Attributes:
        baudrate (int): Serial baud rate.
        timeout (float): Read timeout in seconds.
        serial (Optional[serial.Serial]): PySerial port object when connected.
        logger (logging.Logger): Logger instance for this client.
    """

    def __init__(
        self,
        baudrate: int = SERIAL_BAUDRATE,
        timeout: float = SERIAL_TIMEOUT,
    ) -> None:
        """Initialize serial client.

        Args:
            baudrate: Serial baud rate. Defaults to 115200.
            timeout: Read timeout in seconds. Defaults to 1.0.
                Used for waiting for responses from the digitizer.
        """
        self.baudrate: int = baudrate
        self.timeout: float = timeout
        self.serial: Optional[serial.Serial] = None
        self.logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def list_ports() -> List[str]:
        """List available serial ports on the system.

        Returns:
            List of serial port device paths (e.g., ["/dev/ttyACM0", "/dev/ttyUSB0"]).
            Returns empty list if no ports are found.
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    @staticmethod
    def get_port_info() -> List[Tuple[str, str]]:
        """Get detailed information about available serial ports.

        Returns:
            List of tuples (device_path, description) for each port.
            Example: [("/dev/ttyACM0", "USB Serial Device")]
        """
        ports = serial.tools.list_ports.comports()
        return [(port.device, port.description) for port in ports]

    def connect(self, port: str) -> bool:
        """Connect to a serial port.

        Opens the specified serial port with 8N1 configuration (8 data bits,
        no parity, 1 stop bit) at the configured baud rate.

        Args:
            port: Serial port device path (e.g., "/dev/ttyACM0" or "COM3").

        Returns:
            True if connection succeeded, False if connection failed.
        """
        try:
            self.serial = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self.logger.info(f"Connected to {port} at {self.baudrate} baud")
            return True

        except serial.SerialException as e:
            self.logger.error(f"Failed to connect to {port}: {e}")
            return False

        except Exception as e:
            self.logger.error(f"Unexpected error connecting to {port}: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from serial port and release resources.

        Safe to call multiple times. Suppresses exceptions during
        close but logs errors for debugging.
        """
        if self.serial:
            try:
                self.serial.close()
                self.logger.info("Disconnected from serial port")
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")
            finally:
                self.serial = None

    def is_connected(self) -> bool:
        """Check if currently connected to a serial port.

        Returns:
            True if connected and port is open, False otherwise.
        """
        return self.serial is not None and self.serial.is_open

    def send_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Send command to digitizer and wait for response.

        Transmits the command over serial, waits for the digitizer's response,
        and parses the result. Handles timeouts and decoding errors.

        Args:
            command: Command string without newline terminator
                (e.g., "MOVE 100 200").

        Returns:
            A tuple of (success, error_message) where:
                - success: True if command succeeded (got OK response)
                - error_message: Error message if failed, None if succeeded

        Raises:
            IOError: If not connected to a serial port.
        """
        if not self.is_connected():
            raise IOError("Not connected to serial port")

        try:
            # Add terminator and encode
            command_with_terminator = format_command_for_send(command)
            command_bytes = command_with_terminator.encode('utf-8')

            # Send command
            self.serial.write(command_bytes)
            self.serial.flush()
            self.logger.debug(f"Sent command: {command}")

            # Read response (with timeout)
            response_bytes = self.serial.readline()

            if not response_bytes:
                self.logger.warning("No response from digitizer (timeout)")
                return (False, "No response (timeout)")

            # Decode response
            response = response_bytes.decode('utf-8').strip()
            self.logger.debug(f"Received response: {response}")

            # Parse response
            success, error_msg = parse_response(response)

            if not success:
                self.logger.warning(f"Command failed: {error_msg or 'Unknown error'}")

            return (success, error_msg)

        except serial.SerialException as e:
            error_msg = f"Serial error: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

        except UnicodeDecodeError as e:
            error_msg = f"Response decode error: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def move(self, x: int, y: int) -> Tuple[bool, Optional[str]]:
        """Send MOVE command to move cursor to absolute position.

        Args:
            x: X coordinate (0-32767).
            y: Y coordinate (0-32767).

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.move(x, y)
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format MOVE command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def click(self, button: str) -> Tuple[bool, Optional[str]]:
        """Send CLICK command to perform a button click.

        Args:
            button: Button type - "left" or "right".

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.click(button)
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format CLICK command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def release(self) -> Tuple[bool, Optional[str]]:
        """Send RELEASE command to release all buttons.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.release()
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format RELEASE command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def gesture_start(self) -> Tuple[bool, Optional[str]]:
        """Send GESTURE_START command to start gesture recognition on digitizer.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.gesture_start()
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format GESTURE_START command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def gesture_stop(self) -> Tuple[bool, Optional[str]]:
        """Send GESTURE_STOP command to stop gesture recognition on digitizer.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.gesture_stop()
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format GESTURE_STOP command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def media_play_pause(self) -> Tuple[bool, Optional[str]]:
        """Send MEDIA_PLAY_PAUSE command to toggle media playback.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.media_play_pause()
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format MEDIA_PLAY_PAUSE command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def media_next(self) -> Tuple[bool, Optional[str]]:
        """Send MEDIA_NEXT command to skip to next media track.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.media_next()
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format MEDIA_NEXT command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def media_prev(self) -> Tuple[bool, Optional[str]]:
        """Send MEDIA_PREV command to skip to previous media track.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.media_prev()
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format MEDIA_PREV command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def button_press(self, button: str) -> Tuple[bool, Optional[str]]:
        """Send BUTTON_PRESS command to press a button down.

        Args:
            button: Button type - "left" or "right".

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.button_press(button)
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format BUTTON_PRESS command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def button_release(self, button: str) -> Tuple[bool, Optional[str]]:
        """Send BUTTON_RELEASE command to release a button.

        Args:
            button: Button type - "left" or "right".

        Returns:
            Tuple of (success, error_message).
        """
        try:
            command = CommandFormatter.button_release(button)
            return self.send_command(command)
        except Exception as e:
            error_msg = f"Failed to format BUTTON_RELEASE command: {e}"
            self.logger.error(error_msg)
            return (False, error_msg)

    def __enter__(self) -> "SerialClient":
        """Context manager entry.

        Returns:
            Self for use in with statements.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - disconnects from serial port.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.

        Returns:
            False to propagate any exception that occurred.
        """
        self.disconnect()
        return False
