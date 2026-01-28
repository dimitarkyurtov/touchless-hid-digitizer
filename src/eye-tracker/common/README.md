# Common

This directory contains shared code used by both the host application and the digitizer device. It primarily defines the serial communication protocol, including command constants, coordinate ranges, and parsing/formatting utilities. Both sides import from this module to ensure consistent command handling over the USB serial connection.

## Examples

Formatting a command on the host side:

```python
from common.protocol import CommandFormatter, format_command_for_send

command = CommandFormatter.move(16384, 8192)  # Returns: "MOVE 16384 8192"
serial_port.write(format_command_for_send(command).encode())
```

Parsing a command on the digitizer side:

```python
from common.protocol import CommandParser

cmd_type, params = CommandParser.parse("MOVE 16384 8192")
# cmd_type = "MOVE", params = {"x": 16384, "y": 8192}
```
