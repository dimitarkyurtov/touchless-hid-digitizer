# Common Protocol Library

This directory contains the shared communication protocol implementation used by both the HID digitizer device and the host application.

## Overview

The protocol library provides:
- Command parsing and validation
- Command formatting
- Protocol constants and definitions
- Shared exceptions

Both the digitizer and host applications import from this module to ensure consistent command handling.

## Protocol Specification

### Version

Current protocol version: **1.0.0**

### Transport

- **Medium**: Serial over USB (CDC ACM)
- **Baud Rate**: 115200
- **Format**: 8N1 (8 data bits, no parity, 1 stop bit)
- **Encoding**: ASCII text
- **Terminator**: Newline (`\n`)

### Commands

All commands are ASCII text strings terminated with a newline character.

#### MOVE Command

Move cursor to absolute position.

**Format:**
```
MOVE <x> <y>
```

**Parameters:**
- `x`: X coordinate (integer, 0-32767)
- `y`: Y coordinate (integer, 0-32767)

**Example:**
```
MOVE 16384 8192
```

**Response:**
```
OK
```
or
```
ERROR <message>
```

#### CLICK Command

Perform a button click (press and release).

**Format:**
```
CLICK <button>
```

**Parameters:**
- `button`: Button type, either `left` or `right` (case-insensitive)

**Examples:**
```
CLICK left
CLICK right
```

**Response:**
```
OK
```
or
```
ERROR <message>
```

#### RELEASE Command

Release all buttons.

**Format:**
```
RELEASE
```

**Parameters:** None

**Example:**
```
RELEASE
```

**Response:**
```
OK
```
or
```
ERROR <message>
```

### Responses

The digitizer device sends responses after each command:

- **Success**: `OK\n`
- **Error**: `ERROR <message>\n`

Error messages provide details about what went wrong (e.g., "Invalid coordinates", "Invalid button").

### Coordinate System

The digitizer uses **absolute positioning** with a 16-bit coordinate space:

- **Range**: 0 to 32767 for both X and Y
- **Origin**: Top-left corner (0, 0)
- **Maximum**: Bottom-right corner (32767, 32767)
- **Mapping**: The operating system automatically maps this coordinate space to the physical screen resolution

This coordinate system is defined by the USB HID Digitizer specification and ensures consistent behavior across different screen resolutions.

### Button Types

- **left**: Left mouse button / tip switch (primary button)
- **right**: Right mouse button / barrel switch (secondary button)

## Module Usage

### For Python Applications

#### Parsing Commands (Digitizer Side)

```python
from common.protocol import CommandParser, ProtocolError

try:
    cmd_type, params = CommandParser.parse("MOVE 16384 8192")
    if cmd_type == "MOVE":
        x = params["x"]
        y = params["y"]
        print(f"Move to ({x}, {y})")
except ProtocolError as e:
    print(f"Error: {e}")
```

#### Formatting Commands (Host Side)

```python
from common.protocol import CommandFormatter, format_command_for_send

# Create command
command = CommandFormatter.move(16384, 8192)
# Add terminator for sending
command_to_send = format_command_for_send(command)
# Send over serial
serial_port.write(command_to_send.encode('utf-8'))
```

#### Validating Input

```python
from common.protocol import CommandParser, InvalidCoordinateError

try:
    CommandParser.validate_coordinates(x, y)
    # Coordinates are valid
except InvalidCoordinateError as e:
    print(f"Invalid coordinates: {e}")
```

### Constants

```python
from common.protocol import (
    MIN_COORDINATE,      # 0
    MAX_COORDINATE,      # 32767
    BUTTON_LEFT,         # "left"
    BUTTON_RIGHT,        # "right"
    CMD_MOVE,            # "MOVE"
    CMD_CLICK,           # "CLICK"
    CMD_RELEASE,         # "RELEASE"
    RESPONSE_OK,         # "OK"
    RESPONSE_ERROR,      # "ERROR"
    SERIAL_BAUDRATE,     # 115200
)
```

## Exception Hierarchy

```
ProtocolError (base exception)
├── InvalidCommandError     # Command cannot be parsed
├── InvalidCoordinateError  # Coordinates out of range
└── InvalidButtonError      # Invalid button type
```

## Examples

### Complete Command Exchange

**Host → Digitizer:**
```
MOVE 16384 8192\n
```

**Digitizer → Host:**
```
OK\n
```

**Host → Digitizer:**
```
CLICK left\n
```

**Digitizer → Host:**
```
OK\n
```

**Host → Digitizer:**
```
MOVE 99999 8192\n
```

**Digitizer → Host:**
```
ERROR X coordinate 99999 out of range [0, 32767]\n
```

### Error Handling Example

```python
from common.protocol import (
    CommandParser,
    CommandFormatter,
    ProtocolError,
    InvalidCoordinateError,
    format_command_for_send
)

def send_move(serial_port, x, y):
    """Send MOVE command with error handling."""
    try:
        # Validate coordinates
        CommandParser.validate_coordinates(x, y)

        # Format command
        command = CommandFormatter.move(x, y)
        command_with_terminator = format_command_for_send(command)

        # Send
        serial_port.write(command_with_terminator.encode('utf-8'))
        serial_port.flush()

        # Read response
        response = serial_port.readline().decode('utf-8').strip()

        if response != "OK":
            print(f"Digitizer error: {response}")
            return False

        return True

    except InvalidCoordinateError as e:
        print(f"Invalid coordinates: {e}")
        return False
    except Exception as e:
        print(f"Communication error: {e}")
        return False
```

## Protocol Extensions

Future versions may add:

- Multi-touch support
- Pressure sensitivity
- Tilt/orientation data
- Gesture commands
- Configuration commands

Version negotiation will be added if breaking changes are needed.

## Testing

To test protocol parsing:

```python
from common.protocol import CommandParser

# Test valid commands
assert CommandParser.parse("MOVE 0 0") == ("MOVE", {"x": 0, "y": 0})
assert CommandParser.parse("MOVE 32767 32767") == ("MOVE", {"x": 32767, "y": 32767})
assert CommandParser.parse("CLICK left") == ("CLICK", {"button": "left"})
assert CommandParser.parse("CLICK right") == ("CLICK", {"button": "right"})
assert CommandParser.parse("RELEASE") == ("RELEASE", {})

# Test case insensitivity
assert CommandParser.parse("move 100 200") == ("MOVE", {"x": 100, "y": 200})
assert CommandParser.parse("click LEFT") == ("CLICK", {"button": "left"})

print("All protocol tests passed!")
```

## See Also

- [Main README](../README.md) - Project overview
- [Digitizer README](../digitizer/README.md) - Device setup
- [Host README](../host/README.md) - Host application usage
- [USB HID Usage Tables](https://www.usb.org/document-library/hid-usage-tables-13) - Official HID specification
