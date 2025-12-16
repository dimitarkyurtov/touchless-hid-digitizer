"""Common protocol library for HID Digitizer system.

This module provides shared functionality between the digitizer device
and host application, including command parsing, formatting, and constants.

The protocol supports three main commands:
    - MOVE: Position the cursor at absolute coordinates
    - CLICK: Execute a button click (left or right)
    - RELEASE: Release all buttons

All coordinates are in USB HID Digitizer space (0-32767).

Example:
    Import and use the protocol formatter::

        from common import CommandFormatter
        cmd = CommandFormatter.move(16384, 8192)
        # Returns: "MOVE 16384 8192"

Attributes:
    __version__ (str): Package version following semantic versioning.
"""

__version__ = "1.0.0"

from .protocol import (
    # Constants
    MIN_COORDINATE,
    MAX_COORDINATE,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    CMD_MOVE,
    CMD_CLICK,
    CMD_RELEASE,
    RESPONSE_OK,
    RESPONSE_ERROR,
    # Classes
    CommandParser,
    CommandFormatter,
    # Exceptions
    ProtocolError,
    InvalidCommandError,
    InvalidCoordinateError,
    InvalidButtonError,
)

__all__ = [
    "__version__",
    "MIN_COORDINATE",
    "MAX_COORDINATE",
    "BUTTON_LEFT",
    "BUTTON_RIGHT",
    "CMD_MOVE",
    "CMD_CLICK",
    "CMD_RELEASE",
    "RESPONSE_OK",
    "RESPONSE_ERROR",
    "CommandParser",
    "CommandFormatter",
    "ProtocolError",
    "InvalidCommandError",
    "InvalidCoordinateError",
    "InvalidButtonError",
]
