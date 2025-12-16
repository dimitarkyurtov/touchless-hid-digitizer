# Touchless HID Digitizer

A USB HID digitizer system that allows a host computer to control cursor position and clicks through a connected USB device. This project implements the **standard USB HID Digitizer protocol**, ensuring compatibility with all major operating systems without requiring custom drivers.

## Features

- **Standard HID Digitizer Protocol**: Uses official USB HID specification (Usage Page 0x0D)
- **Cross-Platform Host Support**: Works on macOS, Windows, and Linux
- **Absolute Positioning**: 16-bit coordinate precision (0-32767 range)
- **Button Support**: Left click (tip switch) and right click (barrel switch)
- **Single USB Cable**: Combines HID digitizer and serial communication
- **No Custom Drivers**: Works with native OS HID drivers

## Architecture

```
┌─────────────────────────────────────────────┐
│         Host Computer                       │
│  ┌────────────────────────────────────────┐ │
│  │  Python/Tkinter GUI Application        │ │
│  │  - Input coordinates (X, Y)            │ │
│  │  - Trigger clicks (left/right)         │ │
│  │  - Serial communication                │ │
│  └─────────────────┬──────────────────────┘ │
│                    │                         │
└────────────────────┼─────────────────────────┘
                     │ USB Cable
                     │ (Composite Device: HID + Serial)
┌────────────────────┼─────────────────────────┐
│                    │                         │
│  ┌─────────────────▼──────────────────────┐ │
│  │  Python Service                        │ │
│  │  - Receives serial commands            │ │
│  │  - Generates HID digitizer reports     │ │
│  │  - Controls cursor via HID             │ │
│  └─────────────────┬──────────────────────┘ │
│                    │                         │
│  ┌─────────────────▼──────────────────────┐ │
│  │  USB Gadget (configfs)                 │ │
│  │  - HID Digitizer Function              │ │
│  │  - CDC ACM Serial Function             │ │
│  └────────────────────────────────────────┘ │
│                                              │
│       HID Digitizer Device                  │
│       (e.g., Raspberry Pi)                  │
└──────────────────────────────────────────────┘
```

## Quick Start

### For Digitizer Device Setup

See [digitizer/README.md](digitizer/README.md) for complete installation instructions.

**Summary:**
1. Use hardware with USB OTG support (Raspberry Pi Zero/4, etc.)
2. Install Raspberry Pi OS Lite or equivalent Linux
3. Copy `digitizer/` and `common/` directories to device
4. Follow README instructions to configure USB gadget and install services
5. Connect to host computer via USB

### For Host Application

See [host/README.md](host/README.md) for setup and usage instructions.

**Summary:**
1. Install Python 3.8+ and pip
2. Copy `host/` and `common/` directories
3. Install dependencies: `pip3 install -r host/requirements.txt`
4. Run: `python3 host/main.py`
5. Select serial port and connect

## Communication Protocol

The system uses a simple ASCII-based serial protocol:

- **MOVE x y**: Move cursor to absolute position (x, y in range 0-32767)
- **CLICK button**: Perform click (button = "left" or "right")
- **RELEASE**: Release all buttons

See [common/README.md](common/README.md) for detailed protocol specification.

## Hardware Compatibility

### Digitizer Devices
- **Raspberry Pi Zero W/2W** (Recommended)
- **Raspberry Pi 4** (with USB-C cable supporting data)
- **Raspberry Pi Zero** (original)
- Other Linux devices with USB OTG/gadget support

### Host Operating Systems
- **macOS** 10.15+ (Tested)
- **Windows** 10/11 (Standard HID support)
- **Linux** (with evdev)

## Standard USB HID Digitizer Protocol

This project implements the official USB HID Digitizer specification:

- **Usage Page**: 0x0D (Digitizer)
- **Usage**: 0x04 (Touch Screen)
- **Report Type**: Input
- **Report Size**: 8 bytes
- **Coordinate Range**: 0-32767 (16-bit absolute positioning)
- **Buttons**: Tip Switch (left/touch), Barrel Switch (right click)

The operating system automatically maps the 0-32767 coordinate range to the screen resolution, providing accurate absolute positioning regardless of display size.

**No custom drivers are required** - the device is recognized as a standard USB HID digitizer/tablet by all major operating systems.

## Project Structure

```
touchless-hid-digitizer/
├── README.md                    # This file
├── LICENSE                      # GPL-2.0 license
├── common/                      # Shared protocol library
│   ├── __init__.py
│   ├── protocol.py              # Command parsing and constants
│   └── README.md                # Protocol documentation
├── digitizer/                   # Device-side implementation
│   ├── README.md                # Setup instructions
│   ├── setup-usb-gadget.sh      # USB gadget configuration
│   ├── config.py
│   ├── hid_controller.py        # HID report generation
│   ├── serial_listener.py       # Serial communication
│   ├── main.py                  # Main service
│   ├── requirements.txt
│   ├── usb-gadget.service       # Systemd services
│   └── hid-digitizer.service
└── host/                        # Host application
    ├── README.md                # Usage instructions
    ├── config.py
    ├── serial_client.py         # Serial client
    ├── gui.py                   # Tkinter GUI
    ├── main.py                  # Application entry
    └── requirements.txt
```

## Use Cases

- **Touchless Control Systems**: Control computer via external sensors/cameras
- **Accessibility Tools**: Alternative input methods for users with disabilities
- **Remote Control**: Control host computer from networked device
- **Testing & Automation**: Automate GUI testing with precise cursor control
- **Custom Input Devices**: Build specialized pointing devices

## Technical Details

### HID Report Format

8-byte report structure:
```
[0]    : Button states (bit 0: tip/left, bit 1: barrel/right)
[1-2]  : X coordinate (16-bit little-endian, 0-32767)
[3-4]  : Y coordinate (16-bit little-endian, 0-32767)
[5-6]  : Reserved (0x00)
[7]    : In-range indicator (0x01 when active)
```

### Serial Communication

- **Baud Rate**: 115200
- **Format**: 8N1 (8 data bits, no parity, 1 stop bit)
- **Protocol**: ASCII text commands, newline-terminated
- **Transport**: CDC ACM (USB serial)

## Troubleshooting

### Digitizer not detected on host

1. Check USB cable supports data (not charge-only)
2. Verify USB gadget services are running: `systemctl status usb-gadget.service hid-digitizer.service`
3. Check device files exist: `ls -l /dev/hidg0 /dev/ttyGS0`
4. View logs: `journalctl -u hid-digitizer.service -f`

### Serial port not appearing

1. Verify composite device configuration includes CDC ACM function
2. On macOS: Look for `/dev/cu.usbmodem*`
3. On Linux: Look for `/dev/ttyACM*`
4. On Windows: Check Device Manager for COM ports

### Cursor not moving

1. Verify HID digitizer is recognized:
   - macOS: `system_profiler SPUSBDataType | grep -A 10 Digitizer`
   - Linux: `lsusb -v` and look for HID interface
2. Test manually: `echo -ne '\x01\x00\x40\x00\x40\x00\x00\x01' > /dev/hidg0`
3. Check HID report descriptor is correctly configured

## License

This project is licensed under the GNU General Public License v2.0. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Areas for improvement:

- Support for additional hardware platforms
- Multi-touch/gesture support
- Windows/Linux host application testing
- Protocol extensions
- Documentation improvements

## References

- [USB HID Usage Tables Specification](https://www.usb.org/document-library/hid-usage-tables-13)
- [USB HID Device Class Definition](https://www.usb.org/document-library/device-class-definition-hid-111)
- [Linux USB Gadget API](https://www.kernel.org/doc/html/latest/usb/gadget.html)
- [ConfigFS for USB Gadgets](https://www.kernel.org/doc/html/latest/usb/gadget_configfs.html)

## Authors

Created for touchless computer interaction research and development.
