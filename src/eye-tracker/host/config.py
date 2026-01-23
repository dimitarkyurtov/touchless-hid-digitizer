"""Configuration for HID Digitizer Host Application.

This module contains all configuration settings for the host controller GUI
application. It defines serial communication parameters, coordinate system
constants, GUI layout settings, and visual styling.

The configuration provides sensible defaults for a desktop application
communicating with the HID digitizer device over USB CDC ACM serial.

Constants:
    Serial Communication:
        SERIAL_BAUDRATE (int): Baud rate for serial communication (115200).
        SERIAL_TIMEOUT (float): Read timeout in seconds (1.0).

    Coordinate System:
        MIN_COORDINATE (int): Minimum valid coordinate value (0).
        MAX_COORDINATE (int): Maximum valid coordinate value (32767).
        DEFAULT_X (int): Default X coordinate (16384 - center).
        DEFAULT_Y (int): Default Y coordinate (16384 - center).

    GUI Window:
        WINDOW_TITLE (str): Main window title.
        WINDOW_WIDTH (int): Initial window width in pixels.
        WINDOW_HEIGHT (int): Initial window height in pixels.
        WINDOW_RESIZABLE (bool): Whether window can be resized.

    GUI Layout:
        PADDING (int): Standard padding in pixels.
        LABEL_WIDTH (int): Standard label width in characters.
        ENTRY_WIDTH (int): Standard entry field width in characters.
        BUTTON_WIDTH (int): Standard button width in characters.

    Status Display:
        STATUS_COLOR_CONNECTED (str): Color for connected status (green).
        STATUS_COLOR_DISCONNECTED (str): Color for disconnected status (red).
        STATUS_COLOR_ERROR (str): Color for error status (orange).
        PORT_REFRESH_INTERVAL (int): Port list refresh interval in milliseconds.

    Logging:
        LOG_LEVEL (str): Logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL).
"""

# Serial communication settings
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 1.0  # seconds

# Coordinate system (USB HID Digitizer standard)
MIN_COORDINATE = 0
MAX_COORDINATE = 32767

# GUI settings
WINDOW_TITLE = "HID Digitizer Controller"
WINDOW_WIDTH = 655
WINDOW_HEIGHT = 560
WINDOW_RESIZABLE = False

# Default coordinate values
DEFAULT_X = 16384  # Center X (32767 / 2)
DEFAULT_Y = 16384  # Center Y (32767 / 2)

# GUI Layout
PADDING = 10
LABEL_WIDTH = 15
ENTRY_WIDTH = 10
BUTTON_WIDTH = 15

# Serial port refresh interval (ms)
PORT_REFRESH_INTERVAL = 5000  # 5 seconds

# Status colors
STATUS_COLOR_CONNECTED = "green"
STATUS_COLOR_DISCONNECTED = "red"
STATUS_COLOR_ERROR = "orange"

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
