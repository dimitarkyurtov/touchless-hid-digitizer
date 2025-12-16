"""HID Controller for Digitizer Device.

This module handles HID report generation and transmission according to the
USB HID Digitizer specification. It provides an interface for sending cursor
movement and button click events to the host operating system via the USB
HID gadget device.

HID Report Format (8 bytes):
    Byte 0:   Button states (bit 0: tip/left click, bit 1: barrel/right click)
    Bytes 1-2: X coordinate (16-bit unsigned little-endian, 0-32767)
    Bytes 3-4: Y coordinate (16-bit unsigned little-endian, 0-32767)
    Bytes 5-6: Reserved (always 0x0000)
    Byte 7:   In-range indicator (0x01 when active, 0x00 when out of range)

The HID controller maintains state of the current cursor position and button
states to support relative operations and click events at the current position.

Example:
    Use as a context manager::

        with HIDController() as hid:
            hid.move(16384, 8192)  # Move to center
            hid.click("left")       # Click at current position

    Or manage lifecycle manually::

        hid = HIDController()
        hid.open()
        try:
            hid.move(100, 200)
        finally:
            hid.close()
"""

import logging
import struct
import time
from typing import BinaryIO, Optional

from config import (
    BUTTON_BARREL,
    BUTTON_TIP_SWITCH,
    CLICK_DURATION,
    HID_DEVICE,
    MAX_COORDINATE,
    MIN_COORDINATE,
    REPORT_SIZE,
)


class HIDController:
    """Controls HID digitizer report generation and transmission.

    Generates and sends USB HID reports to the /dev/hidg0 device according
    to the standard USB HID Digitizer specification. Maintains internal state
    for cursor position and button status.

    This class implements the context manager protocol for automatic resource
    management.

    Attributes:
        device_path (str): Path to the HID gadget device file.
        device (Optional[BinaryIO]): File handle to the HID device when open.
        logger (logging.Logger): Logger instance for this controller.
        current_x (int): Last reported X coordinate (0-32767).
        current_y (int): Last reported Y coordinate (0-32767).
        current_buttons (int): Last reported button state bitmask.
    """

    def __init__(self, device_path: str = HID_DEVICE) -> None:
        """Initialize HID controller.

        Args:
            device_path: Path to HID gadget device. Defaults to /dev/hidg0
                as configured in config.HID_DEVICE.
        """
        self.device_path: str = device_path
        self.device: Optional[BinaryIO] = None
        self.logger: logging.Logger = logging.getLogger(__name__)

        # Current state (track last reported values)
        self.current_x: int = 0
        self.current_y: int = 0
        self.current_buttons: int = 0

    def open(self) -> None:
        """Open HID device for writing.

        Opens the HID gadget device in binary write mode with no buffering
        to ensure immediate transmission of HID reports.

        Raises:
            IOError: If the device file cannot be opened (e.g., file doesn't
                exist, insufficient permissions, or device already in use).
        """
        try:
            self.device = open(self.device_path, 'wb', buffering=0)
            self.logger.info(f"Opened HID device: {self.device_path}")
        except IOError as e:
            self.logger.error(f"Failed to open HID device {self.device_path}: {e}")
            raise

    def close(self) -> None:
        """Close HID device and release resources.

        Safe to call multiple times. Suppresses exceptions during close
        but logs errors for debugging.
        """
        if self.device:
            try:
                self.device.close()
                self.logger.info("Closed HID device")
            except Exception as e:
                self.logger.error(f"Error closing HID device: {e}")
            finally:
                self.device = None

    def is_open(self) -> bool:
        """Check if HID device is currently open.

        Returns:
            True if device is open and ready for writing, False otherwise.
        """
        return self.device is not None

    def create_report(
        self,
        x: int,
        y: int,
        buttons: int,
        in_range: bool = True,
    ) -> bytes:
        """Create a USB HID digitizer report.

        Generates an 8-byte HID report according to the USB HID Digitizer
        specification. Coordinates and button values are automatically clamped
        to valid ranges.

        Report format (8 bytes, little-endian):
            [0]:     Button states (bit 0: tip/left, bit 1: barrel/right)
            [1-2]:   X coordinate (16-bit unsigned, 0-32767)
            [3-4]:   Y coordinate (16-bit unsigned, 0-32767)
            [5-6]:   Reserved (always 0x0000)
            [7]:     In-range indicator (0x01 when active, 0x00 when out of range)

        Args:
            x: X coordinate (0-32767). Values outside range are clamped.
            y: Y coordinate (0-32767). Values outside range are clamped.
            buttons: Button bit mask (0-255). Bits are clamped to 8 bits.
            in_range: Whether digitizer is in range. Defaults to True.

        Returns:
            8-byte HID report ready for transmission to /dev/hidg0.

        Note:
            This method does not validate that coordinates are in range.
            Instead, it clamps them to [MIN_COORDINATE, MAX_COORDINATE].
            This is intentional to handle edge cases gracefully.
        """
        # Clamp coordinates to valid range
        x = max(MIN_COORDINATE, min(MAX_COORDINATE, x))
        y = max(MIN_COORDINATE, min(MAX_COORDINATE, y))

        # Clamp buttons to 8-bit value
        buttons = buttons & 0xFF

        # Pack report using little-endian format
        # Format: B = unsigned byte (8-bit)
        #         H = unsigned short (16-bit)
        report = struct.pack(
            '<BHHHHB',
            buttons,              # Byte 0: button states
            x,                    # Bytes 1-2: X coordinate
            y,                    # Bytes 3-4: Y coordinate
            0,                    # Bytes 5-6: reserved
            1 if in_range else 0,  # Byte 7: in-range indicator
        )

        # Verify report size matches configuration
        assert len(report) == REPORT_SIZE, \
            f"Report size mismatch: {len(report)} != {REPORT_SIZE}"

        return report

    def send_report(
        self,
        x: int,
        y: int,
        buttons: int,
        in_range: bool = True,
    ) -> None:
        """Generate and send HID report to the device.

        Creates an HID report and writes it to the HID gadget device.
        Updates internal state to track the last sent position and button states.

        Args:
            x: X coordinate (0-32767).
            y: Y coordinate (0-32767).
            buttons: Button bit mask.
            in_range: Whether digitizer is in range. Defaults to True.

        Raises:
            IOError: If device is not open or report transmission fails.
        """
        if not self.is_open():
            raise IOError("HID device not open")

        report = self.create_report(x, y, buttons, in_range)

        try:
            self.device.write(report)
            self.device.flush()

            # Update current state after successful transmission
            self.current_x = x
            self.current_y = y
            self.current_buttons = buttons

            self.logger.debug(
                f"Sent HID report: x={x}, y={y}, buttons=0x{buttons:02x}, "
                f"in_range={in_range}"
            )

        except IOError as e:
            self.logger.error(f"Failed to send HID report: {e}")
            raise

    def move(self, x: int, y: int) -> None:
        """Move cursor to absolute position without button press.

        Args:
            x: X coordinate (0-32767).
            y: Y coordinate (0-32767).

        Raises:
            IOError: If device is not open or transmission fails.
        """
        self.send_report(x, y, 0, True)
        self.logger.info(f"Moved to ({x}, {y})")

    def click(self, button: str) -> None:
        """Perform button click (press and release) at current position.

        Executes a complete click sequence: press button, hold for
        CLICK_DURATION, then release. The cursor remains at the current
        position throughout the click.

        Args:
            button: Button type - "left" or "right" (case-insensitive).

        Raises:
            IOError: If device is not open or transmission fails.

        Note:
            Invalid button names are logged as errors but do not raise
            exceptions, allowing the service to continue running.
        """
        # Determine button mask
        button_lower = button.lower()
        if button_lower == "left":
            button_mask = BUTTON_TIP_SWITCH
            button_name = "left"
        elif button_lower == "right":
            button_mask = BUTTON_BARREL
            button_name = "right"
        else:
            self.logger.error(f"Invalid button: {button}")
            return

        # Press button at current position
        self.send_report(self.current_x, self.current_y, button_mask, True)
        self.logger.debug(f"Pressed {button_name} button")

        # Hold for configured click duration
        time.sleep(CLICK_DURATION)

        # Release button
        self.send_report(self.current_x, self.current_y, 0, True)
        self.logger.debug(f"Released {button_name} button")

        self.logger.info(
            f"Clicked {button_name} button at ({self.current_x}, {self.current_y})"
        )

    def release(self) -> None:
        """Release all buttons at current position.

        Sends a report with no buttons pressed, maintaining the current
        cursor position.

        Raises:
            IOError: If device is not open or transmission fails.
        """
        self.send_report(self.current_x, self.current_y, 0, True)
        self.logger.info("Released all buttons")

    def reset(self) -> None:
        """Reset digitizer to default state.

        Moves cursor to origin (0, 0) and releases all buttons.

        Raises:
            IOError: If device is not open or transmission fails.
        """
        self.send_report(0, 0, 0, True)
        self.logger.info("Reset digitizer to (0, 0)")

    def __enter__(self) -> "HIDController":
        """Context manager entry - opens the HID device.

        Returns:
            Self for use in with statements.

        Raises:
            IOError: If device cannot be opened.
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - closes the HID device.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.

        Returns:
            False to propagate any exception that occurred.
        """
        self.close()
        return False
