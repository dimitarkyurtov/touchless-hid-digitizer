# Digitizer Device

This component is designed to run on a Linux-based system with USB OTG support (such as a Raspberry Pi). It operates as a standard systemd user-space service that receives HID commands from the host application over USB serial and translates them into USB HID reports. The system uses the Linux USB gadget subsystem via configfs to present itself to the host computer as a composite USB device containing both an HID digitizer (for cursor control) and a CDC ACM serial interface (for receiving commands). No kernel modifications are required - the service writes directly to `/dev/hidg0` to send HID reports to the operating system.

## Installation

### Step 1: Clone Repository

```bash
cd ~
git clone https://github.com/anthropics/touchless-hid-digitizer.git
cd touchless-hid-digitizer
```

Or copy the `src/eye-tracker/digitizer/` and `src/eye-tracker/common/` directories manually.

### Step 2: Install Python Dependencies Globally

```bash
cd ~/touchless-hid-digitizer/src/eye-tracker/digitizer
pip install -r requirements.txt
```

### Step 3: Enable USB Gadget Mode

Edit the boot configuration:

```bash
# For newer Raspberry Pi OS (bookworm and later)
sudo nano /boot/firmware/config.txt

# For older Raspberry Pi OS
# sudo nano /boot/config.txt
```

Add at the end:

```
dtoverlay=dwc2
```

Edit modules configuration:

```bash
sudo nano /etc/modules
```

Add at the end:

```
dwc2
libcomposite
```

### Step 4: Copy Application Files

```bash
sudo mkdir -p /opt/hid-digitizer
sudo cp -r ~/touchless-hid-digitizer/src/eye-tracker/digitizer /opt/touchless-hid-digitizer/eye-tracker/
sudo cp -r ~/touchless-hid-digitizer/src/eye-tracker/common /opt/touchless-hid-digitizer/eye-tracker/
sudo chmod +x /opt/hid-digitizer/main.py
```

### Step 5: Install USB Gadget Setup Script

```bash
sudo cp /opt/touchless-hid-digitizer/eye-tracker/digitizer/setup-usb-gadget.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/setup-usb-gadget.sh
```

### Step 6: Install Systemd Services

```bash
sudo cp /opt/touchless-hid-digitizer/eye-tracker/digitizer/usb-gadget.service /etc/systemd/system/
sudo cp /opt/touchless-hid-digitizer/eye-tracker/digitizer/hid-digitizer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable usb-gadget.service
sudo systemctl enable hid-digitizer.service
```

### Step 7: Reboot

```bash
sudo reboot
```

### Step 8: Verify Installation

```bash
sudo systemctl status usb-gadget.service
sudo systemctl status hid-digitizer.service
ls -l /dev/hidg0 /dev/ttyGS0
```

Both services should show "active" and both device files should exist.

### Step 9: Watch Live Logs

```bash
sudo journalctl -u hid-digitizer.service -n 30 -f
```
