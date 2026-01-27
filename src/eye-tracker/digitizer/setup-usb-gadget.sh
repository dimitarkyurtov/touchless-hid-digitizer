#!/bin/bash
#
# USB Gadget Configuration for HID Digitizer + Serial
#
# This script configures a Raspberry Pi (or other Linux device) as a composite
# USB device with both HID digitizer and CDC ACM (serial) functions.
#
# The HID descriptor implements the standard USB HID Digitizer protocol
# (Usage Page 0x0D, Usage 0x04) for absolute cursor positioning.
#

set -e

# USB Device Configuration
VENDOR_ID="0x1d6b"           # Linux Foundation
PRODUCT_ID="0x0104"          # Multifunction Composite Gadget
DEVICE_VERSION="0x0100"      # Version 1.0.0
USB_VERSION="0x0200"         # USB 2.0

# Device Strings
SERIAL_NUMBER="fedcba9876543210"
MANUFACTURER="DIY HID Digitizer"
PRODUCT="Touchless HID Digitizer"
CONFIGURATION_NAME="HID Digitizer + Serial"

# Gadget Configuration
GADGET_NAME="hiddigitizer"
GADGET_DIR="/sys/kernel/config/usb_gadget/${GADGET_NAME}"
CONFIG_NAME="c.1"
MAX_POWER="250"  # mA

# HID Configuration
HID_PROTOCOL="2"     # Mouse protocol
HID_SUBCLASS="1"     # Boot interface subclass (mouse)
HID_REPORT_LENGTH="6"

# HID Report Descriptor for Mouse/Pointer
# This descriptor defines an absolute positioning mouse device:
# - Usage Page: 0x01 (Generic Desktop)
# - Usage: 0x02 (Mouse) with absolute coordinates
# - Absolute X/Y coordinates (0-32767)
# - Two buttons: Button 1 (left click) and Button 2 (right click)
#
# Report format (6 bytes):
# [0]   : Report ID (0x01)
# [1]   : Button states (bit 0: button 1, bit 1: button 2)
# [2-3] : X coordinate (16-bit little-endian)
# [4-5] : Y coordinate (16-bit little-endian)

HID_REPORT_DESC="
05 01                    // Usage Page (Generic Desktop)
09 02                    // Usage (Mouse)
a1 01                    // Collection (Application)
85 01                    //   Report ID (1)
09 01                    //   Usage (Pointer)
a1 00                    //   Collection (Physical)
05 09                    //     Usage Page (Button)
19 01                    //     Usage Minimum (Button 1)
29 02                    //     Usage Maximum (Button 2)
15 00                    //     Logical Minimum (0)
25 01                    //     Logical Maximum (1)
75 01                    //     Report Size (1 bit)
95 02                    //     Report Count (2)
81 02                    //     Input (Data, Variable, Absolute)
75 06                    //     Report Size (6 bits)
95 01                    //     Report Count (1)
81 03                    //     Input (Constant) - padding
05 01                    //     Usage Page (Generic Desktop)
09 30                    //     Usage (X)
09 31                    //     Usage (Y)
16 00 00                 //     Logical Minimum (0)
26 ff 7f                 //     Logical Maximum (32767)
75 10                    //     Report Size (16 bits)
95 02                    //     Report Count (2)
81 02                    //     Input (Data, Variable, Absolute)
c0                       //   End Collection
c0                       // End Collection
"

# Consumer Control HID Report Descriptor
# Implements media key controls: Play/Pause, Next Track, Previous Track
# Report format (2 bytes): [Report ID=0x02] [bit0: Play/Pause, bit1: Next, bit2: Prev, bits3-7: padding]
HID_CONSUMER_REPORT_DESC="
05 0C                    // Usage Page (Consumer)
09 01                    // Usage (Consumer Control)
a1 01                    // Collection (Application)
85 02                    //   Report ID (2)
15 00                    //   Logical Minimum (0)
25 01                    //   Logical Maximum (1)
75 01                    //   Report Size (1)
95 03                    //   Report Count (3)
09 CD                    //   Usage (Play/Pause)
09 B5                    //   Usage (Scan Next Track)
09 B6                    //   Usage (Scan Previous Track)
81 02                    //   Input (Data, Variable, Absolute)
75 05                    //   Report Size (5)
95 01                    //   Report Count (1)
81 03                    //   Input (Constant) - padding
c0                       // End Collection
"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# Function to check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log "ERROR: This script must be run as root"
        exit 1
    fi
}

# Function to detect USB Device Controller
detect_udc() {
    local udc_list=$(ls /sys/class/udc 2>/dev/null)
    if [ -z "$udc_list" ]; then
        log "ERROR: No USB Device Controller (UDC) found"
        log "Make sure USB gadget support is enabled in the kernel"
        exit 1
    fi
    echo "$udc_list" | head -n1
}

# Function to remove existing gadget
remove_gadget() {
    if [ ! -d "$GADGET_DIR" ]; then
        return 0
    fi

    log "Removing existing gadget..."

    # Disable gadget
    if [ -f "${GADGET_DIR}/UDC" ]; then
        echo "" > "${GADGET_DIR}/UDC" 2>/dev/null || true
    fi

    # Remove configuration symlinks
    rm -f "${GADGET_DIR}/configs/${CONFIG_NAME}/hid.usb0" 2>/dev/null || true
    rm -f "${GADGET_DIR}/configs/${CONFIG_NAME}/hid.usb1" 2>/dev/null || true
    rm -f "${GADGET_DIR}/configs/${CONFIG_NAME}/acm.usb0" 2>/dev/null || true

    # Remove functions
    if [ -d "${GADGET_DIR}/functions/hid.usb0" ]; then
        rmdir "${GADGET_DIR}/functions/hid.usb0" 2>/dev/null || true
    fi
    if [ -d "${GADGET_DIR}/functions/hid.usb1" ]; then
        rmdir "${GADGET_DIR}/functions/hid.usb1" 2>/dev/null || true
    fi
    if [ -d "${GADGET_DIR}/functions/acm.usb0" ]; then
        rmdir "${GADGET_DIR}/functions/acm.usb0" 2>/dev/null || true
    fi

    # Remove strings
    rmdir "${GADGET_DIR}/configs/${CONFIG_NAME}/strings/0x409" 2>/dev/null || true
    rmdir "${GADGET_DIR}/configs/${CONFIG_NAME}" 2>/dev/null || true
    rmdir "${GADGET_DIR}/strings/0x409" 2>/dev/null || true

    # Remove gadget directory
    rmdir "${GADGET_DIR}" 2>/dev/null || true

    log "Existing gadget removed"
}

# Function to convert hex string to binary for HID descriptor
hex_to_binary() {
    local hex_string="$1"
    # Remove spaces, newlines, and comments
    hex_string=$(echo "$hex_string" | sed 's://.*$::g' | tr -d ' \n\r\t')
    # Convert hex to binary
    echo -n "$hex_string" | xxd -r -p
}

# Main setup function
setup_gadget() {
    local udc

    log "Starting USB gadget setup..."

    # Detect UDC
    udc=$(detect_udc)
    log "Using USB Device Controller: $udc"

    # Create gadget directory
    log "Creating gadget directory..."
    mkdir -p "$GADGET_DIR"
    cd "$GADGET_DIR"

    # Set USB device identifiers
    log "Configuring device identifiers..."
    echo "$VENDOR_ID" > idVendor
    echo "$PRODUCT_ID" > idProduct
    echo "$DEVICE_VERSION" > bcdDevice
    echo "$USB_VERSION" > bcdUSB

    # Set device class (0x00 = use interface descriptors)
    echo "0x00" > bDeviceClass
    echo "0x00" > bDeviceSubClass
    echo "0x00" > bDeviceProtocol

    # Create English strings
    log "Creating device strings..."
    mkdir -p strings/0x409
    echo "$SERIAL_NUMBER" > strings/0x409/serialnumber
    echo "$MANUFACTURER" > strings/0x409/manufacturer
    echo "$PRODUCT" > strings/0x409/product

    # Create configuration
    log "Creating configuration..."
    mkdir -p "configs/${CONFIG_NAME}"
    mkdir -p "configs/${CONFIG_NAME}/strings/0x409"
    echo "$CONFIGURATION_NAME" > "configs/${CONFIG_NAME}/strings/0x409/configuration"
    echo "$MAX_POWER" > "configs/${CONFIG_NAME}/MaxPower"
    echo "0x80" > "configs/${CONFIG_NAME}/bmAttributes"  # Bus-powered

    # Create HID function
    log "Creating HID digitizer function..."
    mkdir -p functions/hid.usb0
    echo "$HID_PROTOCOL" > functions/hid.usb0/protocol
    echo "$HID_SUBCLASS" > functions/hid.usb0/subclass
    echo "$HID_REPORT_LENGTH" > functions/hid.usb0/report_length

    # Write HID report descriptor
    log "Writing HID report descriptor..."
    hex_to_binary "$HID_REPORT_DESC" > functions/hid.usb0/report_desc

    # Create Consumer Control HID function
    log "Creating Consumer Control HID function..."
    mkdir -p functions/hid.usb1
    echo "0" > functions/hid.usb1/protocol
    echo "0" > functions/hid.usb1/subclass
    echo "2" > functions/hid.usb1/report_length

    # Write Consumer Control HID report descriptor
    log "Writing Consumer Control HID report descriptor..."
    hex_to_binary "$HID_CONSUMER_REPORT_DESC" > functions/hid.usb1/report_desc

    # Create CDC ACM (Serial) function
    log "Creating CDC ACM serial function..."
    mkdir -p functions/acm.usb0

    # Link functions to configuration
    log "Linking functions to configuration..."
    ln -s functions/hid.usb0 "configs/${CONFIG_NAME}/"
    ln -s functions/hid.usb1 "configs/${CONFIG_NAME}/"
    ln -s functions/acm.usb0 "configs/${CONFIG_NAME}/"

    # Enable gadget
    log "Enabling USB gadget..."
    echo "$udc" > UDC

    log "USB gadget configured successfully!"
    log "HID device: /dev/hidg0"
    log "Consumer Control HID device: /dev/hidg1"
    log "Serial device: /dev/ttyGS0"
}

# Main execution
main() {
    check_root
    remove_gadget
    setup_gadget
    log "Setup complete"
}

main
