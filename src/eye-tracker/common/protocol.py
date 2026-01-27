"""HID Digitizer Communication Protocol.

This module defines the communication protocol between the host application
and the HID digitizer device. It provides command parsing, formatting, and
validation functionality shared by both components.

The protocol uses ASCII-based commands sent over USB CDC ACM serial:
    - MOVE <x> <y>: Move cursor to absolute coordinates
    - CLICK <button>: Click a button (left or right)
    - RELEASE: Release all buttons

Responses from the digitizer:
    - OK: Command executed successfully
    - ERROR [message]: Command failed with optional error message

Protocol Version: 1.0.0

Examples:
    Parse a command::

        from common.protocol import CommandParser
        cmd_type, params = CommandParser.parse("MOVE 16384 8192")
        # cmd_type = "MOVE", params = {"x": 16384, "y": 8192}

    Format a command::

        from common.protocol import CommandFormatter
        cmd = CommandFormatter.move(16384, 8192)
        # Returns: "MOVE 16384 8192"
"""

import re
from typing import Any, Dict, Optional, Tuple

# Protocol version
PROTOCOL_VERSION = "1.0.0"

# Coordinate constants
MIN_COORDINATE = 0
MAX_COORDINATE = 32767  # Maximum value for 16-bit signed coordinate

# Button constants
BUTTON_LEFT = "left"
BUTTON_RIGHT = "right"
VALID_BUTTONS = {BUTTON_LEFT, BUTTON_RIGHT}

# Command constants
CMD_MOVE = "MOVE"
CMD_CLICK = "CLICK"
CMD_RELEASE = "RELEASE"
CMD_GESTURE_START = "GESTURE_START"
CMD_GESTURE_STOP = "GESTURE_STOP"

# Response constants
RESPONSE_OK = "OK"
RESPONSE_ERROR = "ERROR"

# Serial communication constants
SERIAL_BAUDRATE = 115200
SERIAL_TERMINATOR = "\n"


# Exceptions


class ProtocolError(Exception):
    """Base exception for all protocol-related errors.

    This is the parent exception class for all protocol errors.
    Catch this to handle any protocol-related issue.
    """


class InvalidCommandError(ProtocolError):
    """Raised when a command string cannot be parsed.

    This exception is raised when the command format doesn't match
    any known command pattern (MOVE, CLICK, RELEASE).

    Attributes:
        message (str): Description of the parsing error.
    """


class InvalidCoordinateError(ProtocolError):
    """Raised when coordinates are out of valid range.

    Coordinates must be in the range [0, 32767] as per USB HID
    Digitizer specification.

    Attributes:
        message (str): Description including the invalid value and valid range.
    """


class InvalidButtonError(ProtocolError):
    """Raised when button type is invalid.

    Valid button types are 'left' and 'right'.

    Attributes:
        message (str): Description of the invalid button type.
    """


# Command Parser


class CommandParser:
    """Parses commands from the serial protocol.

    This class is used by the digitizer device to interpret ASCII commands
    received from the host application over the serial connection.

    The parser validates command syntax and coordinate/button values,
    raising appropriate exceptions for malformed input.

    Class Attributes:
        MOVE_PATTERN (re.Pattern): Regex pattern for MOVE commands.
        CLICK_PATTERN (re.Pattern): Regex pattern for CLICK commands.
        RELEASE_PATTERN (re.Pattern): Regex pattern for RELEASE commands.

    Examples:
        Parse a MOVE command::

            cmd_type, params = CommandParser.parse("MOVE 16384 8192")
            # Returns: ("MOVE", {"x": 16384, "y": 8192})

        Parse a CLICK command::

            cmd_type, params = CommandParser.parse("CLICK left")
            # Returns: ("CLICK", {"button": "left"})
    """

    # Regex patterns for command parsing
    MOVE_PATTERN = re.compile(r'^MOVE\s+(\d+)\s+(\d+)$', re.IGNORECASE)
    CLICK_PATTERN = re.compile(r'^CLICK\s+(left|right)$', re.IGNORECASE)
    RELEASE_PATTERN = re.compile(r'^RELEASE$', re.IGNORECASE)
    GESTURE_START_PATTERN = re.compile(r'^GESTURE_START$', re.IGNORECASE)
    GESTURE_STOP_PATTERN = re.compile(r'^GESTURE_STOP$', re.IGNORECASE)

    @staticmethod
    def parse(command_str: str) -> Tuple[str, Dict[str, Any]]:
        """Parse a command string into command type and parameters.

        Args:
            command_str: Command string to parse (without newline terminator).
                The string is case-insensitive and will be normalized to uppercase.

        Returns:
            A tuple of (command_type, parameters_dict) where:
                - command_type: One of CMD_MOVE, CMD_CLICK, or CMD_RELEASE
                - parameters_dict: Dictionary with command-specific parameters:
                    - MOVE: {"x": int, "y": int}
                    - CLICK: {"button": str}  # "left" or "right"
                    - RELEASE: {}  # empty dict

        Raises:
            InvalidCommandError: If command format is invalid or unrecognized.
            InvalidCoordinateError: If MOVE coordinates are out of range [0, 32767].
            InvalidButtonError: If CLICK button is not "left" or "right".

        Examples:
            >>> CommandParser.parse("MOVE 16384 8192")
            ('MOVE', {'x': 16384, 'y': 8192})

            >>> CommandParser.parse("CLICK left")
            ('CLICK', {'button': 'left'})

            >>> CommandParser.parse("RELEASE")
            ('RELEASE', {})
        """
        command_str = command_str.strip().upper()

        if not command_str:
            raise InvalidCommandError("Empty command")

        # Try to parse MOVE command
        match = CommandParser.MOVE_PATTERN.match(command_str)
        if match:
            x = int(match.group(1))
            y = int(match.group(2))

            # Validate coordinates
            if not (MIN_COORDINATE <= x <= MAX_COORDINATE):
                raise InvalidCoordinateError(
                    f"X coordinate {x} out of range [{MIN_COORDINATE}, {MAX_COORDINATE}]"
                )
            if not (MIN_COORDINATE <= y <= MAX_COORDINATE):
                raise InvalidCoordinateError(
                    f"Y coordinate {y} out of range [{MIN_COORDINATE}, {MAX_COORDINATE}]"
                )

            return (CMD_MOVE, {"x": x, "y": y})

        # Try to parse CLICK command
        match = CommandParser.CLICK_PATTERN.match(command_str)
        if match:
            button = match.group(1).lower()

            # Validate button
            if button not in VALID_BUTTONS:
                raise InvalidButtonError(f"Invalid button: {button}")

            return (CMD_CLICK, {"button": button})

        # Try to parse RELEASE command
        if CommandParser.RELEASE_PATTERN.match(command_str):
            return (CMD_RELEASE, {})

        # Try to parse GESTURE_START command
        if CommandParser.GESTURE_START_PATTERN.match(command_str):
            return (CMD_GESTURE_START, {})

        # Try to parse GESTURE_STOP command
        if CommandParser.GESTURE_STOP_PATTERN.match(command_str):
            return (CMD_GESTURE_STOP, {})

        # No pattern matched
        raise InvalidCommandError(f"Unknown command: {command_str}")

    @staticmethod
    def validate_coordinates(x: int, y: int) -> None:
        """Validate that coordinate values are within valid range.

        Coordinates must be in the range [0, 32767] as defined by the
        USB HID Digitizer specification.

        Args:
            x: X coordinate to validate.
            y: Y coordinate to validate.

        Raises:
            InvalidCoordinateError: If either coordinate is outside the
                valid range [MIN_COORDINATE, MAX_COORDINATE].
        """
        if not (MIN_COORDINATE <= x <= MAX_COORDINATE):
            raise InvalidCoordinateError(
                f"X coordinate {x} out of range [{MIN_COORDINATE}, {MAX_COORDINATE}]"
            )
        if not (MIN_COORDINATE <= y <= MAX_COORDINATE):
            raise InvalidCoordinateError(
                f"Y coordinate {y} out of range [{MIN_COORDINATE}, {MAX_COORDINATE}]"
            )

    @staticmethod
    def validate_button(button: str) -> None:
        """Validate that button type is valid.

        Args:
            button: Button type string to validate. Case-insensitive.

        Raises:
            InvalidButtonError: If button is not "left" or "right" (case-insensitive).
        """
        if button.lower() not in VALID_BUTTONS:
            raise InvalidButtonError(
                f"Invalid button '{button}'. Must be one of: {', '.join(VALID_BUTTONS)}"
            )


# Command Formatter


class CommandFormatter:
    """Formats commands for sending over the serial protocol.

    This class is used by the host application to generate properly
    formatted ASCII command strings for transmission to the digitizer device.

    All methods validate input parameters before formatting, raising
    appropriate exceptions for invalid values.

    Examples:
        Format a MOVE command::

            cmd = CommandFormatter.move(16384, 8192)
            # Returns: "MOVE 16384 8192"

        Format a CLICK command::

            cmd = CommandFormatter.click("left")
            # Returns: "CLICK left"
    """

    @staticmethod
    def move(x: int, y: int) -> str:
        """Format a MOVE command with absolute coordinates.

        Args:
            x: X coordinate in digitizer space (0-32767).
            y: Y coordinate in digitizer space (0-32767).

        Returns:
            Formatted command string without newline terminator.
            Format: "MOVE <x> <y>"

        Raises:
            InvalidCoordinateError: If coordinates are out of valid range.

        Example:
            >>> CommandFormatter.move(16384, 8192)
            'MOVE 16384 8192'
        """
        CommandParser.validate_coordinates(x, y)
        return f"{CMD_MOVE} {x} {y}"

    @staticmethod
    def click(button: str) -> str:
        """Format a CLICK command for a button press-and-release.

        Args:
            button: Button type - either "left" or "right" (case-insensitive).

        Returns:
            Formatted command string without newline terminator.
            Format: "CLICK <button>" where button is lowercased.

        Raises:
            InvalidButtonError: If button is not "left" or "right".

        Example:
            >>> CommandFormatter.click("left")
            'CLICK left'
        """
        CommandParser.validate_button(button)
        return f"{CMD_CLICK} {button.lower()}"

    @staticmethod
    def release() -> str:
        """Format a RELEASE command to release all buttons.

        Returns:
            Formatted command string without newline terminator.
            Always returns: "RELEASE"

        Example:
            >>> CommandFormatter.release()
            'RELEASE'
        """
        return CMD_RELEASE

    @staticmethod
    def gesture_start() -> str:
        """Format a GESTURE_START command to start gesture recognition.

        Returns:
            Formatted command string without newline terminator.
            Always returns: "GESTURE_START"

        Example:
            >>> CommandFormatter.gesture_start()
            'GESTURE_START'
        """
        return CMD_GESTURE_START

    @staticmethod
    def gesture_stop() -> str:
        """Format a GESTURE_STOP command to stop gesture recognition.

        Returns:
            Formatted command string without newline terminator.
            Always returns: "GESTURE_STOP"

        Example:
            >>> CommandFormatter.gesture_stop()
            'GESTURE_STOP'
        """
        return CMD_GESTURE_STOP

    @staticmethod
    def format_response(success: bool, message: str = "") -> str:
        """Format a response message from the digitizer.

        Used by the digitizer to format acknowledgment messages.

        Args:
            success: True for OK response, False for ERROR response.
            message: Optional error message to include with ERROR response.
                Ignored if success is True.

        Returns:
            Formatted response string without newline terminator.
            Format: "OK" if success, "ERROR [message]" if not.

        Examples:
            >>> CommandFormatter.format_response(True)
            'OK'

            >>> CommandFormatter.format_response(False, "Invalid coordinates")
            'ERROR Invalid coordinates'

            >>> CommandFormatter.format_response(False)
            'ERROR'
        """
        if success:
            return RESPONSE_OK

        if message:
            return f"{RESPONSE_ERROR} {message}"
        return RESPONSE_ERROR


# Helper functions


def format_command_for_send(command: str) -> str:
    """Add newline terminator to command string for serial transmission.

    Args:
        command: Command string without terminator (e.g., "MOVE 100 200").

    Returns:
        Command string with newline terminator appended.

    Example:
        >>> format_command_for_send("MOVE 100 200")
        'MOVE 100 200\\n'
    """
    return command + SERIAL_TERMINATOR


def parse_response(response_str: str) -> Tuple[bool, Optional[str]]:
    """Parse a response string from the digitizer.

    Parses acknowledgment responses to determine if a command succeeded
    or failed, extracting error messages when present.

    Args:
        response_str: Response string from digitizer, with or without
            newline terminator.

    Returns:
        A tuple of (success, error_message) where:
            - success: True if response is "OK", False otherwise
            - error_message: Error message text if present, None if no message
                or if response was OK

    Examples:
        >>> parse_response("OK")
        (True, None)

        >>> parse_response("ERROR Invalid coordinates")
        (False, 'Invalid coordinates')

        >>> parse_response("ERROR")
        (False, None)

        >>> parse_response("INVALID")
        (False, 'Unknown response: INVALID')
    """
    response_str = response_str.strip()

    if response_str == RESPONSE_OK:
        return (True, None)

    if response_str.startswith(RESPONSE_ERROR):
        # Extract error message after "ERROR" prefix
        error_msg = response_str[len(RESPONSE_ERROR):].strip()
        return (False, error_msg if error_msg else None)

    # Unknown response format - treat as error
    return (False, f"Unknown response: {response_str}")
