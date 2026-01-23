# HID Digitizer Host Application

This directory contains the host-side application for controlling the HID digitizer device. It provides a cross-platform graphical user interface (GUI) for sending commands to the digitizer over USB serial.

## Features

- **Cross-Platform**: Works on macOS, Windows, and Linux
- **Simple GUI**: Tkinter-based interface for easy coordinate input
- **Preset Positions**: Quick buttons for common positions (center, corners)
- **Combined Actions**: Move + click in one action
- **Real-Time Feedback**: Status indicators and error messages
- **Serial Port Detection**: Automatic detection of available ports

## Prerequisites

### Software Requirements

- **Python**: 3.8 or newer
- **pip**: Python package installer

**Check your Python version:**

```bash
python3 --version
```

### Platform-Specific Notes

#### macOS

Python 3 is typically pre-installed. If not:

```bash
# Using Homebrew
brew install python3
```

#### Windows

Download and install Python from [python.org](https://www.python.org/downloads/).

Make sure to check "Add Python to PATH" during installation.

#### Linux

Python 3 is usually pre-installed. If not:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip

# Fedora
sudo dnf install python3 python3-pip

# Arch
sudo pacman -S python python-pip
```

## Installation

### Step 1: Get the Code

Clone the repository or download and extract it:

```bash
git clone https://github.com/yourusername/touchless-hid-digitizer.git
cd touchless-hid-digitizer/host
```

Or if you only want the host application, copy the `host/` and `common/` directories to your computer.

### Step 2: Install Dependencies

Navigate to the `host` directory and install required Python packages:

```bash
cd host
pip3 install -r requirements.txt
```

On some systems, you might need to use `pip` instead of `pip3`:

```bash
pip install -r requirements.txt
```

**Note for Linux users**: You may need to add your user to the `dialout` group to access serial ports without sudo:

```bash
sudo usermod -a -G dialout $USER
# Log out and log back in for this to take effect
```

### Step 3: Verify Installation

Test that the application can start:

```bash
python3 main.py
```

The GUI window should appear. You can close it for now.

## Usage

### Starting the Application

```bash
cd host
python3 main.py
```

On Windows, you can also double-click `main.py` if Python file associations are configured.

### Connecting to Digitizer

1. **Connect the digitizer device** to your computer via USB
2. **Wait a few seconds** for the device to be recognized
3. **Click "Refresh"** to update the list of serial ports
4. **Select the digitizer's serial port** from the dropdown:
   - **macOS**: `/dev/cu.usbmodem*` (e.g., `/dev/cu.usbmodem14201`)
   - **Linux**: `/dev/ttyACM*` (e.g., `/dev/ttyACM0`)
   - **Windows**: `COM*` (e.g., `COM3` or `COM4`)
5. **Click "Connect"**
6. Status should change to "Connected" in green

### Using the Controls

#### Coordinate Input

- **X and Y fields**: Enter absolute coordinates (0-32767)
- **Coordinate space**: The digitizer uses 16-bit absolute positioning
  - `0, 0` = Top-left corner
  - `16384, 16384` = Center of screen
  - `32767, 32767` = Bottom-right corner
- Your operating system automatically maps these coordinates to your screen resolution

#### Preset Buttons

- **Center**: Sets coordinates to (16384, 16384)
- **Top-Left**: Sets coordinates to (0, 0)
- **Bottom-Right**: Sets coordinates to (32767, 32767)

#### Action Buttons

- **Move**: Move cursor to the specified coordinates
- **Left Click**: Perform left mouse button click at current position
- **Right Click**: Perform right mouse button click at current position
- **Move + Left Click**: Move to coordinates then perform left click
- **Move + Right Click**: Move to coordinates then perform right click
- **Release**: Release all buttons (if stuck)

### Tips

1. **Start with Center**: Use the "Center" preset and "Move" to verify the connection works
2. **Use Combined Actions**: The "Move + Click" buttons are convenient for single operations
3. **Coordinate Calculation**:
   - To find coordinates for a pixel position on a 1920×1080 screen:
     - X: `(pixel_x / 1920) × 32767`
     - Y: `(pixel_y / 1080) × 32767`
4. **Testing**: Use "Move" commands to see the cursor move without clicking

## Troubleshooting

### Serial Port Not Found

**Symptoms**: No ports appear in the dropdown, or "No ports found" is displayed.

**Solutions**:

1. **Check USB connection**: Ensure the digitizer device is connected via USB
2. **Check cable**: Use a data-capable USB cable (not charge-only)
3. **Wait for enumeration**: Give the device 5-10 seconds to be recognized
4. **Check device recognition**:

   **macOS**:
   ```bash
   ls -l /dev/cu.*
   # Look for /dev/cu.usbmodem*
   ```

   **Linux**:
   ```bash
   ls -l /dev/ttyACM*
   # Check dmesg for device connection
   dmesg | tail
   ```

   **Windows**:
   - Open Device Manager
   - Look under "Ports (COM & LPT)"
   - The digitizer should appear as a COM port

5. **Install drivers** (Windows only):
   - Windows usually installs CDC ACM drivers automatically
   - If not, you may need to install the USB CDC driver

### Permission Denied (Linux)

**Symptom**: Error connecting to serial port with "Permission denied"

**Solution**:

```bash
# Add your user to dialout group
sudo usermod -a -G dialout $USER

# Log out and log back in, or use:
newgrp dialout

# Check permissions
ls -l /dev/ttyACM0
```

### Connection Failed

**Symptom**: "Failed to connect" error when clicking Connect

**Solutions**:

1. **Close other applications**: Ensure no other program is using the serial port
2. **Restart digitizer**: Unplug and reconnect the digitizer device
3. **Check digitizer service**: On the digitizer device, verify the service is running (see digitizer README)
4. **Try different port**: If multiple ports are listed, try each one

### Commands Not Working

**Symptom**: Connection succeeds but commands don't move the cursor

**Solutions**:

1. **Check digitizer logs**: On the digitizer device, check service logs
2. **Verify HID device**: Ensure the digitizer appears as an HID device on the host
3. **Test manually**: Use `screen` or similar to send commands directly
4. **Check response**: The application shows error messages if the digitizer reports problems

### Application Won't Start

**Symptom**: Error when running `python3 main.py`

**Solutions**:

1. **Check Python version**: Must be 3.8 or newer
   ```bash
   python3 --version
   ```

2. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Check for import errors**: Run with verbose output
   ```bash
   python3 -v main.py
   ```

4. **Verify file structure**: Ensure both `host/` and `common/` directories are present

## Advanced Usage

### Command-Line Mode

For automation or testing, you can use the serial client directly in Python:

```python
#!/usr/bin/env python3
from host.serial_client import SerialClient

# Create client
client = SerialClient()

# Connect
if client.connect("/dev/cu.usbmodem14201"):
    # Move cursor
    success, error = client.move(16384, 8192)
    if success:
        print("Moved successfully")

    # Click
    success, error = client.click("left")
    if success:
        print("Clicked successfully")

    # Disconnect
    client.disconnect()
```

### Coordinate Conversion

To convert screen pixel coordinates to digitizer coordinates:

```python
def pixel_to_digitizer(pixel_x, pixel_y, screen_width, screen_height):
    """Convert pixel coordinates to digitizer coordinates."""
    dig_x = int((pixel_x / screen_width) * 32767)
    dig_y = int((pixel_y / screen_height) * 32767)
    return dig_x, dig_y

# Example: Convert (960, 540) on a 1920x1080 screen
dig_x, dig_y = pixel_to_digitizer(960, 540, 1920, 1080)
print(f"Digitizer coordinates: ({dig_x}, {dig_y})")  # (16384, 16384)
```

### Configuration

Edit `config.py` to customize:

- Window size and title
- Default coordinate values
- Serial timeout
- GUI colors and layout

## Cross-Platform Compatibility

### macOS

- Fully supported and tested
- Serial ports appear as `/dev/cu.usbmodem*`
- No additional drivers needed

### Linux

- Fully supported
- Serial ports appear as `/dev/ttyACM*`
- May need to add user to `dialout` group for permissions
- Works with X11 and Wayland

### Windows

- Supported (tested on Windows 10/11)
- Serial ports appear as `COM3`, `COM4`, etc.
- USB CDC drivers usually install automatically
- May need to check Device Manager if port doesn't appear

## See Also

- [Main README](../README.md) - Project overview
- [Protocol Documentation](../common/README.md) - Communication protocol details
- [Digitizer Setup](../digitizer/README.md) - Device-side setup instructions

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review the [main README](../README.md)
3. Check digitizer device logs
4. Open an issue on GitHub

## License

This project is licensed under the GNU General Public License v2.0. See [LICENSE](../LICENSE) for details.
