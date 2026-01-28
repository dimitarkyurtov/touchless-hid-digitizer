# HID Digitizer Device Setup

This directory contains the device-side implementation of the HID digitizer system. It runs on hardware with USB OTG (On-The-Go) support, such as a Raspberry Pi, and presents itself to the host computer as a standard USB HID digitizer device.

## Project Structure

```
src/eye-tracker/
├── common/                    # Shared code between host and digitizer
│   ├── __init__.py
│   ├── camera.py              # Camera wrapper class
│   ├── gesture_types.py       # GestureType enum (shared)
│   └── protocol.py            # Serial communication protocol
├── digitizer/                 # Raspberry Pi device code (this directory)
│   ├── config.py              # Device configuration
│   ├── hid_controller.py      # USB HID report generation
│   ├── main.py                # Main service entry point
│   ├── serial_listener.py     # Serial command listener
│   ├── setup-usb-gadget.sh    # USB gadget configuration script
│   ├── hid-digitizer.service  # Systemd service for main app
│   └── usb-gadget.service     # Systemd service for USB gadget
└── host/                      # Mac/PC host application
    ├── gui.py                 # Tkinter GUI
    ├── serial_client.py       # Serial communication client
    ├── eye_tracker.py         # Eye tracking module
    ├── hand_gesture_recognizer.py  # Hand gesture recognition
    └── ...
```

## Architecture

The digitizer acts as a command executor, receiving commands from the host via USB serial and translating them into HID reports:

```
Host (Mac/PC)                          Digitizer (Raspberry Pi)
┌─────────────────────┐                ┌─────────────────────────┐
│ Eye Tracking        │                │                         │
│ + Gesture Recognition│──── USB ─────▶│  Serial Listener        │
│ (runs locally)      │    Serial      │         │               │
│                     │                │         ▼               │
│ Serial Commands:    │                │  Command Parser         │
│ - MOVE x y          │                │         │               │
│ - BUTTON_PRESS left │                │         ▼               │
│ - MEDIA_PLAY_PAUSE  │                │  HID Controller         │
│ - etc.              │                │         │               │
└─────────────────────┘                │         ▼               │
                                       │  /dev/hidg0 ──▶ OS      │
                                       └─────────────────────────┘
```

**Note**: Hand gesture recognition runs on the host machine (Mac/PC) for better performance. The host sends explicit button press/release and media control commands to the digitizer.

## Supported Commands

The digitizer accepts the following commands over serial:

| Command | Description |
|---------|-------------|
| `MOVE x y` | Move cursor to absolute coordinates (0-32767) |
| `CLICK left\|right` | Click and release a button |
| `RELEASE` | Release all buttons |
| `BUTTON_PRESS left\|right` | Press and hold a button |
| `BUTTON_RELEASE left\|right` | Release a held button |
| `MEDIA_PLAY_PAUSE` | Toggle media play/pause |
| `MEDIA_NEXT` | Skip to next track |
| `MEDIA_PREV` | Skip to previous track |

## Prerequisites

### Hardware Requirements

**Supported Devices:**
- **Raspberry Pi Zero W / Zero 2 W** (Recommended - has USB OTG)
- **Raspberry Pi 4** (requires USB-C cable with data support)
- **Raspberry Pi Zero** (original)
- Other Linux-based devices with USB gadget/OTG support

**USB Cable:**
- Must support data transfer (not charge-only)
- For Pi Zero: Micro-USB cable
- For Pi 4: USB-C cable (must support data mode)

### Software Requirements

- **Operating System**: Raspberry Pi OS Lite (Debian-based Linux)
  - Download: https://www.raspberrypi.com/software/operating-systems/
  - Recommended: Latest Raspberry Pi OS Lite (64-bit or 32-bit)
- **Python**: 3.7 or newer (included in Raspberry Pi OS)
- **Root access**: Required for USB gadget configuration and HID device access

## Installation

### Step 1: Clone Repository

On your Raspberry Pi, clone or copy the repository:

```bash
cd ~
git clone https://github.com/yourusername/touchless-hid-digitizer.git
cd touchless-hid-digitizer
```

Or copy the `src/eye-tracker/digitizer/` and `src/eye-tracker/common/` directories manually via SCP/SFTP.

### Step 2: Install Python Dependencies

**IMPORTANT**: Use a virtual environment to avoid conflicts with system packages.

```bash
cd ~/touchless-hid-digitizer/src/eye-tracker/digitizer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Enable USB Gadget Mode

Edit the boot configuration to enable the dwc2 USB driver:

**Note**: On newer Raspberry Pi OS, the config file is at `/boot/firmware/config.txt` instead of `/boot/config.txt`.

```bash
# For newer Raspberry Pi OS (bookworm and later)
sudo nano /boot/firmware/config.txt

# For older Raspberry Pi OS
# sudo nano /boot/config.txt
```

Add this line at the end:

```
dtoverlay=dwc2
```

Save and exit (Ctrl+X, then Y, then Enter).

Edit the modules configuration to load required kernel modules:

```bash
sudo nano /etc/modules
```

Add these lines at the end:

```
dwc2
libcomposite
```

Save and exit.

**Important**: The `libcomposite` module is required for USB gadget configfs support.

### Step 4: Copy Application Files

Copy the application to `/opt/hid-digitizer/`:

```bash
sudo mkdir -p /opt/hid-digitizer

# Copy digitizer code
sudo cp -r ~/touchless-hid-digitizer/src/eye-tracker/digitizer/* /opt/hid-digitizer/

# Copy common code (required for protocol)
sudo cp -r ~/touchless-hid-digitizer/src/eye-tracker/common /opt/hid-digitizer/
```

Make the main script executable:

```bash
sudo chmod +x /opt/hid-digitizer/main.py
```

### Step 5: Install USB Gadget Setup Script

Copy the USB gadget configuration script:

```bash
sudo cp /opt/hid-digitizer/setup-usb-gadget.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/setup-usb-gadget.sh
```

### Step 6: Install Systemd Services

Copy the systemd service files:

```bash
sudo cp /opt/hid-digitizer/usb-gadget.service /etc/systemd/system/
sudo cp /opt/hid-digitizer/hid-digitizer.service /etc/systemd/system/
```

Reload systemd and enable services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable usb-gadget.service
sudo systemctl enable hid-digitizer.service
```

### Step 7: Reboot

Reboot the Raspberry Pi to apply changes:

```bash
sudo reboot
```

### Step 8: Verify Installation

After reboot, check that services are running:

```bash
sudo systemctl status usb-gadget.service
sudo systemctl status hid-digitizer.service
```

Both should show "active (running)" or "active (exited)" for usb-gadget.

Verify device files exist:

```bash
ls -l /dev/hidg0 /dev/ttyGS0
```

You should see both devices.

Check logs:

```bash
sudo journalctl -u hid-digitizer.service -f
```

You should see "Service ready, listening for commands..."

## Configuration

### Modifying Settings

Edit `/opt/hid-digitizer/config.py` to change:

- Device paths (`/dev/hidg0`, `/dev/ttyGS0`)
- Serial baud rate (default: 115200)
- Click duration (default: 50ms)
- Logging level and paths

After changes, restart the service:

```bash
sudo systemctl restart hid-digitizer.service
```

### USB Gadget Customization

Edit `/usr/local/bin/setup-usb-gadget.sh` to customize:

- USB Vendor ID and Product ID
- Device manufacturer and product strings
- Serial number

After changes:

```bash
sudo systemctl restart usb-gadget.service
sudo systemctl restart hid-digitizer.service
```

## Usage

### Connecting to Host

1. Connect Raspberry Pi to host computer via USB cable
2. Wait ~5 seconds for device enumeration
3. Check host computer recognizes the device:

**On macOS:**
```bash
system_profiler SPUSBDataType | grep -A 10 "Digitizer"
```

**On Linux:**
```bash
lsusb | grep "Digitizer"
```

**On Windows:**
- Open Device Manager
- Look for HID-compliant device under "Human Interface Devices"

### Serial Port

The serial port will appear on the host as:

- **macOS**: `/dev/cu.usbmodem*` (e.g., `/dev/cu.usbmodem14201`)
- **Linux**: `/dev/ttyACM*` (e.g., `/dev/ttyACM0`)
- **Windows**: `COM*` (e.g., `COM3`)

The host application will connect to this serial port to send commands.

### Manual Testing

You can test the digitizer manually using the serial port:

**From host computer:**

```bash
# macOS/Linux:
screen /dev/cu.usbmodem14201 115200

# Then type commands:
MOVE 16384 16384
CLICK left
BUTTON_PRESS left
BUTTON_RELEASE left
MEDIA_PLAY_PAUSE
RELEASE
```

You should see the cursor move on the host screen and the "OK" response in the terminal.

## Troubleshooting

### Services Not Starting

**Check USB gadget service:**
```bash
sudo systemctl status usb-gadget.service
sudo journalctl -u usb-gadget.service
```

**Common issues:**
- ConfigFS not mounted: Check if `/sys/kernel/config` exists
- UDC not found: Check if `ls /sys/class/udc` shows your USB controller
- Permission errors: Service must run as root

**Solution:**
```bash
# Check if configfs is mounted
mount | grep configfs

# If not, mount it
sudo mount -t configfs none /sys/kernel/config

# Try running setup script manually
sudo /usr/local/bin/setup-usb-gadget.sh
```

### HID Device Not Found

**Check if /dev/hidg0 exists:**
```bash
ls -l /dev/hidg0
```

**If missing:**
- Verify usb-gadget service ran successfully
- Check `lsmod | grep usb_f_hid` - should show module loaded
- Reboot and check again

### Serial Device Not Found

**Check if /dev/ttyGS0 exists:**
```bash
ls -l /dev/ttyGS0
```

**If missing:**
- Verify USB gadget includes ACM function
- Check `lsmod | grep g_serial` or `lsmod | grep usb_f_acm`

### Permission Errors

The HID digitizer service needs root access to write to `/dev/hidg0`.

**Check service runs as root:**
```bash
sudo systemctl status hid-digitizer.service | grep "User"
```

**Solution:**
Service file should have `User=root` or no User specified (defaults to root).

### Cursor Not Moving on Host

1. **Verify HID device is recognized on host**

**macOS:**
```bash
system_profiler SPUSBDataType
```
Look for device with class "Human Interface Device"

**Linux:**
```bash
lsusb -v | grep -A 20 "Digitizer"
```

2. **Test HID device manually on Raspberry Pi:**

```bash
# Send a test report (move to center)
echo -ne '\x00\x00\x40\x00\x40\x00\x00\x01' | sudo tee /dev/hidg0
```

The cursor should move on the host screen.

3. **Check logs for errors:**

```bash
sudo journalctl -u hid-digitizer.service -n 50
```

### Host Not Seeing Serial Port

**Check host device list:**

**macOS:**
```bash
ls -l /dev/cu.*
```

**Linux:**
```bash
ls -l /dev/ttyACM*
```

**Windows:**
- Device Manager → Ports (COM & LPT)

**If not found:**
- Check USB cable supports data (not charge-only)
- Try a different USB port
- Check `dmesg` on host when connecting device
- Verify composite device includes CDC ACM function

## Adapting to Other Hardware

This implementation can be adapted to other hardware with USB gadget support:

### Requirements

1. Linux kernel with CONFIG_USB_GADGET enabled
2. USB Device Controller (UDC) hardware
3. ConfigFS support (CONFIG_USB_CONFIGFS)
4. Python 3.7+

### Changes Needed

1. **USB Controller**: Update `UDC` variable in `setup-usb-gadget.sh`
   ```bash
   UDC=$(ls /sys/class/udc | head -n1)
   ```

2. **Device Paths**: May differ on some systems
   - Check actual paths for HID and serial gadget devices
   - Update `config.py` if different

3. **Boot Configuration**: Varies by device
   - Raspberry Pi uses `/boot/config.txt`
   - Other devices may use device tree overlays or kernel parameters

4. **Systemd**: If not using systemd, adapt to your init system

## Logs and Debugging

### View Logs

```bash
# Real-time log viewing
sudo journalctl -u hid-digitizer.service -f

# Last 100 lines
sudo journalctl -u hid-digitizer.service -n 100

# Logs since last boot
sudo journalctl -u hid-digitizer.service -b

# Log file (if enabled in config)
sudo tail -f /var/log/hid-digitizer.log
```

### Enable Debug Logging

Edit `/opt/hid-digitizer/config.py`:

```python
LOG_LEVEL = "DEBUG"
```

Restart service:

```bash
sudo systemctl restart hid-digitizer.service
```

### Test Without Service

Run the application directly for debugging:

```bash
cd /opt/hid-digitizer
sudo venv/bin/python3 main.py
```

Press Ctrl+C to stop.

## Uninstallation

To remove the HID digitizer:

```bash
# Stop and disable services
sudo systemctl stop hid-digitizer.service
sudo systemctl stop usb-gadget.service
sudo systemctl disable hid-digitizer.service
sudo systemctl disable usb-gadget.service

# Remove files
sudo rm /etc/systemd/system/hid-digitizer.service
sudo rm /etc/systemd/system/usb-gadget.service
sudo rm /usr/local/bin/setup-usb-gadget.sh
sudo rm -rf /opt/hid-digitizer

# Reload systemd
sudo systemctl daemon-reload

# Remove boot configuration
sudo nano /boot/config.txt  # Remove dtoverlay=dwc2 line
sudo nano /etc/modules      # Remove dwc2 line

# Reboot
sudo reboot
```

## See Also

- [Main Project README](../../../README.md) - Project overview
- [Protocol Documentation](../common/README.md) - Communication protocol
- [Host Application](../host/README.md) - Host setup and usage
- [Linux USB Gadget Documentation](https://www.kernel.org/doc/html/latest/usb/gadget.html)
