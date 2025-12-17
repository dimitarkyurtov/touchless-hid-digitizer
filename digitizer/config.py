"""Configuration for HID Digitizer Device.

This module contains all configuration settings for the HID digitizer service
running on the Raspberry Pi. It defines device paths, serial communication
parameters, HID report settings, and logging configuration.

The configuration uses sensible defaults for a Raspberry Pi setup with USB
gadget mode enabled. Paths and parameters can be modified to match specific
hardware configurations.

Constants:
    Device Paths:
        HID_DEVICE (str): Path to the HID gadget device (/dev/hidg0).
        SERIAL_DEVICE (str): Path to the CDC ACM serial device (/dev/ttyGS0).

    Serial Communication:
        SERIAL_BAUDRATE (int): Baud rate for serial communication (115200).
        SERIAL_TIMEOUT (float): Read timeout in seconds (1.0).

    HID Report Configuration:
        REPORT_SIZE (int): Size of HID report in bytes (8).
        HID_REPORT_INTERVAL (float): Minimum interval between reports in seconds.
        BUTTON_TIP_SWITCH (int): Bit mask for left click/touch (0x01).
        BUTTON_BARREL (int): Bit mask for right click (0x02).

    Coordinate System:
        MIN_COORDINATE (int): Minimum valid coordinate value (0).
        MAX_COORDINATE (int): Maximum valid coordinate value (32767).

    Click Behavior:
        CLICK_DURATION (float): Duration to hold button pressed in seconds (0.05).

    Logging:
        LOG_LEVEL (str): Logging level (INFO).
        LOG_FILE (str): Path to log file.
        LOG_TO_CONSOLE (bool): Enable console logging.
        LOG_TO_FILE (bool): Enable file logging.

    Service:
        SERVICE_NAME (str): Name of the systemd service.
        RECONNECT_DELAY (int): Delay before reconnection attempts in seconds.
"""

import os
from pathlib import Path

# Device paths
HID_DEVICE = "/dev/hidg0"         # HID gadget device
SERIAL_DEVICE = "/dev/ttyGS0"     # Serial gadget device (CDC ACM)

# Serial communication settings
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 1.0  # seconds

# HID report settings
REPORT_SIZE = 6  # bytes (Report ID + buttons + X + Y)
HID_REPORT_INTERVAL = 0.001  # seconds between reports (1ms)

# Button bit masks (for HID report byte 0)
BUTTON_TIP_SWITCH = 0x01  # Bit 0: Left click / touch
BUTTON_BARREL = 0x02      # Bit 1: Right click

# Coordinate limits (from USB HID Digitizer spec)
MIN_COORDINATE = 0
MAX_COORDINATE = 32767

# Click duration
CLICK_DURATION = 0.05  # seconds (50ms press before release)

# Logging configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "/var/log/hid-digitizer.log"
LOG_TO_CONSOLE = True
LOG_TO_FILE = True

# Create log directory if it doesn't exist
# Falls back to /tmp if /var/log is not writable
_LOG_DIR = os.path.dirname(LOG_FILE)
if _LOG_DIR and not os.path.exists(_LOG_DIR):
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except OSError:
        # If we can't create /var/log, fall back to /tmp
        LOG_FILE = "/tmp/hid-digitizer.log"

# Service settings
SERVICE_NAME = "hid-digitizer"
RECONNECT_DELAY = 5  # seconds to wait before reconnecting on error
