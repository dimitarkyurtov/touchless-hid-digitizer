"""Tkinter GUI for HID Digitizer Controller.

This module provides a graphical user interface for controlling the HID digitizer
device. The GUI allows users to manually send commands to the digitizer, including
cursor movement and button clicks.

The interface includes:
    - Serial port selection and connection management
    - Manual coordinate input with preset buttons
    - Action buttons for move, click, and release commands
    - Real-time status display
    - Information panel explaining the coordinate system

The GUI is built using Tkinter and follows a modular design with separate
methods for building different sections of the interface.

In future versions, this GUI will be extended to support:
    - Eye tracking visualization and calibration
    - Real-time eye position display
    - Gesture control visualization
    - Performance monitoring

Example:
    Create and run the GUI::

        app = HIDDigitizerGUI()
        app.run()
"""

import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional, Tuple

# Add parent directory to path to import common module
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.protocol import MAX_COORDINATE, MIN_COORDINATE
from config import (
    BUTTON_WIDTH,
    DEFAULT_X,
    DEFAULT_Y,
    PADDING,
    STATUS_COLOR_CONNECTED,
    STATUS_COLOR_DISCONNECTED,
    STATUS_COLOR_ERROR,
    WINDOW_HEIGHT,
    WINDOW_RESIZABLE,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from serial_client import SerialClient


class HIDDigitizerGUI:
    """Main GUI application for HID digitizer control.

    Provides a Tkinter-based graphical interface for controlling the HID
    digitizer device. Manages serial connection, coordinate input, and
    command transmission.

    The GUI is organized into sections:
        - Serial port connection panel
        - Coordinate input panel with presets
        - Action buttons panel
        - Information panel

    Attributes:
        logger (logging.Logger): Logger instance for this GUI.
        serial_client (SerialClient): Serial communication client.
        root (tk.Tk): Main Tkinter window.
        port_var (tk.StringVar): Selected serial port variable.
        port_combo (ttk.Combobox): Port selection combobox.
        connect_btn (ttk.Button): Connect/disconnect button.
        status_var (tk.StringVar): Connection status text variable.
        status_label (ttk.Label): Status display label.
        x_var (tk.StringVar): X coordinate input variable.
        x_entry (ttk.Entry): X coordinate entry field.
        y_var (tk.StringVar): Y coordinate input variable.
        y_entry (ttk.Entry): Y coordinate entry field.
    """

    def __init__(self) -> None:
        """Initialize GUI components and window.

        Creates the main window, initializes the serial client,
        builds the GUI layout, and sets up event handlers.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.serial_client: SerialClient = SerialClient()

        # Create main window
        self.root: tk.Tk = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(WINDOW_RESIZABLE, WINDOW_RESIZABLE)

        # Build GUI components
        self.build_gui()

        # Set up window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_gui(self) -> None:
        """Build all GUI components.

        Constructs the complete GUI layout by calling individual section
        builders in sequence. Each section returns the next available row
        number for vertical layout.
        """
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding=PADDING)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Build sections
        row = 0
        row = self.build_serial_section(main_frame, row)
        row = self.build_coordinates_section(main_frame, row)
        row = self.build_actions_section(main_frame, row)
        row = self.build_info_section(main_frame, row)

        # Initialize port list
        self.refresh_ports()

    def build_serial_section(self, parent: ttk.Frame, start_row: int) -> int:
        """
        Build serial port selection section.

        Args:
            parent: Parent frame
            start_row: Starting row number

        Returns:
            Next available row number
        """
        # Serial port frame
        port_frame = ttk.LabelFrame(parent, text="Serial Port Connection", padding=PADDING)
        port_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, PADDING))
        port_frame.columnconfigure(0, weight=1)

        # Port selection row
        port_select_frame = ttk.Frame(port_frame)
        port_select_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        port_select_frame.columnconfigure(0, weight=1)

        ttk.Label(port_select_frame, text="Port:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            port_select_frame,
            textvariable=self.port_var,
            state='readonly',
            width=30
        )
        self.port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Button(
            port_select_frame,
            text="Refresh",
            command=self.refresh_ports,
            width=10
        ).grid(row=0, column=2, padx=(0, 5))

        self.connect_btn = ttk.Button(
            port_select_frame,
            text="Connect",
            command=self.toggle_connection,
            width=10
        )
        self.connect_btn.grid(row=0, column=3)

        # Status label
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(
            port_frame,
            textvariable=self.status_var,
            foreground=STATUS_COLOR_DISCONNECTED,
            font=('TkDefaultFont', 9, 'bold')
        )
        self.status_label.grid(row=1, column=0, pady=(5, 0))

        return start_row + 1

    def build_coordinates_section(self, parent: ttk.Frame, start_row: int) -> int:
        """
        Build coordinates input section.

        Args:
            parent: Parent frame
            start_row: Starting row number

        Returns:
            Next available row number
        """
        # Coordinates frame
        coord_frame = ttk.LabelFrame(parent, text="Coordinates", padding=PADDING)
        coord_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, PADDING))

        # X coordinate
        ttk.Label(coord_frame, text="X:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.x_var = tk.StringVar(value=str(DEFAULT_X))
        self.x_entry = ttk.Entry(coord_frame, textvariable=self.x_var, width=10)
        self.x_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

        # Y coordinate
        ttk.Label(coord_frame, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.y_var = tk.StringVar(value=str(DEFAULT_Y))
        self.y_entry = ttk.Entry(coord_frame, textvariable=self.y_var, width=10)
        self.y_entry.grid(row=0, column=3, sticky=tk.W)

        # Range label
        range_text = f"Range: {MIN_COORDINATE} - {MAX_COORDINATE}"
        ttk.Label(
            coord_frame,
            text=range_text,
            font=('TkDefaultFont', 8)
        ).grid(row=1, column=0, columnspan=4, pady=(5, 0))

        # Preset buttons
        preset_frame = ttk.Frame(coord_frame)
        preset_frame.grid(row=2, column=0, columnspan=4, pady=(10, 0))

        ttk.Button(
            preset_frame,
            text="Center",
            command=lambda: self.set_coordinates(16384, 16384),
            width=10
        ).grid(row=0, column=0, padx=2)

        ttk.Button(
            preset_frame,
            text="Top-Left",
            command=lambda: self.set_coordinates(0, 0),
            width=10
        ).grid(row=0, column=1, padx=2)

        ttk.Button(
            preset_frame,
            text="Bottom-Right",
            command=lambda: self.set_coordinates(32767, 32767),
            width=10
        ).grid(row=0, column=2, padx=2)

        return start_row + 1

    def build_actions_section(self, parent: ttk.Frame, start_row: int) -> int:
        """
        Build action buttons section.

        Args:
            parent: Parent frame
            start_row: Starting row number

        Returns:
            Next available row number
        """
        # Actions frame
        action_frame = ttk.LabelFrame(parent, text="Actions", padding=PADDING)
        action_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, PADDING))

        # Configure grid
        for i in range(3):
            action_frame.columnconfigure(i, weight=1)

        # Row 1: Move, Left Click, Right Click
        ttk.Button(
            action_frame,
            text="Move",
            command=self.send_move,
            width=BUTTON_WIDTH
        ).grid(row=0, column=0, padx=5, pady=5)

        ttk.Button(
            action_frame,
            text="Left Click",
            command=self.send_left_click,
            width=BUTTON_WIDTH
        ).grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(
            action_frame,
            text="Right Click",
            command=self.send_right_click,
            width=BUTTON_WIDTH
        ).grid(row=0, column=2, padx=5, pady=5)

        # Row 2: Move + Left Click, Move + Right Click, Release
        ttk.Button(
            action_frame,
            text="Move + Left Click",
            command=self.send_move_and_left_click,
            width=BUTTON_WIDTH
        ).grid(row=1, column=0, padx=5, pady=5)

        ttk.Button(
            action_frame,
            text="Move + Right Click",
            command=self.send_move_and_right_click,
            width=BUTTON_WIDTH
        ).grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(
            action_frame,
            text="Release",
            command=self.send_release,
            width=BUTTON_WIDTH
        ).grid(row=1, column=2, padx=5, pady=5)

        return start_row + 1

    def build_info_section(self, parent: ttk.Frame, start_row: int) -> int:
        """
        Build info section.

        Args:
            parent: Parent frame
            start_row: Starting row number

        Returns:
            Next available row number
        """
        # Info frame
        info_frame = ttk.LabelFrame(parent, text="Information", padding=PADDING)
        info_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E))

        info_text = (
            "The digitizer uses absolute coordinates (0-32767).\n"
            "Your OS automatically maps this to your screen resolution.\n"
            "Center: (16384, 16384)  •  Top-Left: (0, 0)  •  Bottom-Right: (32767, 32767)"
        )

        ttk.Label(
            info_frame,
            text=info_text,
            font=('TkDefaultFont', 8),
            justify=tk.LEFT
        ).grid(row=0, column=0, sticky=tk.W)

        return start_row + 1

    def refresh_ports(self) -> None:
        """Refresh available serial ports."""
        ports = SerialClient.list_ports()

        if not ports:
            self.port_combo['values'] = ["No ports found"]
            self.port_combo.current(0)
            self.logger.warning("No serial ports found")
        else:
            self.port_combo['values'] = ports
            self.port_combo.current(0)
            self.logger.info(f"Found {len(ports)} serial port(s)")

    def toggle_connection(self) -> None:
        """Connect or disconnect from serial port."""
        if self.serial_client.is_connected():
            # Disconnect
            self.serial_client.disconnect()
            self.update_connection_status(False)
        else:
            # Connect
            port = self.port_var.get()

            if not port or port == "No ports found":
                messagebox.showerror("Error", "No serial port selected")
                return

            if self.serial_client.connect(port):
                self.update_connection_status(True, port)
            else:
                messagebox.showerror("Error", f"Failed to connect to {port}")
                self.update_connection_status(False)

    def update_connection_status(self, connected: bool, port: str = "") -> None:
        """
        Update connection status display.

        Args:
            connected: Whether connected
            port: Port name if connected
        """
        if connected:
            self.status_var.set(f"Connected to {port}")
            self.status_label.config(foreground=STATUS_COLOR_CONNECTED)
            self.connect_btn.config(text="Disconnect")
        else:
            self.status_var.set("Disconnected")
            self.status_label.config(foreground=STATUS_COLOR_DISCONNECTED)
            self.connect_btn.config(text="Connect")

    def set_coordinates(self, x: int, y: int) -> None:
        """
        Set coordinate values in GUI.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.x_var.set(str(x))
        self.y_var.set(str(y))

    def validate_coordinates(self) -> Optional[Tuple[int, int]]:
        """Validate and return coordinates from GUI input fields.

        Reads X and Y values from the entry fields, validates that they are
        integers within the valid range, and displays error dialogs if not.

        Returns:
            Tuple of (x, y) if coordinates are valid integers in range,
            None if validation fails.
        """
        try:
            x = int(self.x_var.get())
            y = int(self.y_var.get())

            if not (MIN_COORDINATE <= x <= MAX_COORDINATE):
                messagebox.showerror(
                    "Error",
                    f"X coordinate must be between {MIN_COORDINATE} and {MAX_COORDINATE}"
                )
                return None

            if not (MIN_COORDINATE <= y <= MAX_COORDINATE):
                messagebox.showerror(
                    "Error",
                    f"Y coordinate must be between {MIN_COORDINATE} and {MAX_COORDINATE}"
                )
                return None

            return (x, y)

        except ValueError:
            messagebox.showerror("Error", "Coordinates must be integers")
            return None

    def check_connected(self) -> bool:
        """
        Check if connected, show error if not.

        Returns:
            True if connected, False otherwise
        """
        if not self.serial_client.is_connected():
            messagebox.showwarning("Warning", "Not connected to digitizer")
            return False
        return True

    def handle_command_result(self, success: bool, error_msg: Optional[str]) -> None:
        """
        Handle command result.

        Args:
            success: Whether command succeeded
            error_msg: Error message if failed
        """
        if not success:
            messagebox.showerror("Command Failed", error_msg or "Unknown error")
            self.status_label.config(foreground=STATUS_COLOR_ERROR)

    def send_move(self) -> None:
        """Send MOVE command."""
        if not self.check_connected():
            return

        coords = self.validate_coordinates()
        if coords:
            x, y = coords
            success, error_msg = self.serial_client.move(x, y)
            self.handle_command_result(success, error_msg)
            if success:
                self.logger.info(f"Moved to ({x}, {y})")

    def send_left_click(self) -> None:
        """Send left CLICK command."""
        if not self.check_connected():
            return

        success, error_msg = self.serial_client.click("left")
        self.handle_command_result(success, error_msg)
        if success:
            self.logger.info("Left click sent")

    def send_right_click(self) -> None:
        """Send right CLICK command."""
        if not self.check_connected():
            return

        success, error_msg = self.serial_client.click("right")
        self.handle_command_result(success, error_msg)
        if success:
            self.logger.info("Right click sent")

    def send_move_and_left_click(self) -> None:
        """Send MOVE followed by left CLICK."""
        if not self.check_connected():
            return

        coords = self.validate_coordinates()
        if coords:
            x, y = coords

            # Move
            success, error_msg = self.serial_client.move(x, y)
            if not success:
                self.handle_command_result(success, error_msg)
                return

            # Click
            success, error_msg = self.serial_client.click("left")
            self.handle_command_result(success, error_msg)
            if success:
                self.logger.info(f"Moved to ({x}, {y}) and clicked left")

    def send_move_and_right_click(self) -> None:
        """Send MOVE followed by right CLICK."""
        if not self.check_connected():
            return

        coords = self.validate_coordinates()
        if coords:
            x, y = coords

            # Move
            success, error_msg = self.serial_client.move(x, y)
            if not success:
                self.handle_command_result(success, error_msg)
                return

            # Click
            success, error_msg = self.serial_client.click("right")
            self.handle_command_result(success, error_msg)
            if success:
                self.logger.info(f"Moved to ({x}, {y}) and clicked right")

    def send_release(self) -> None:
        """Send RELEASE command."""
        if not self.check_connected():
            return

        success, error_msg = self.serial_client.release()
        self.handle_command_result(success, error_msg)
        if success:
            self.logger.info("Release sent")

    def on_closing(self) -> None:
        """Handle window close event.

        Called when the user closes the window. Disconnects from serial
        port if connected and destroys the Tkinter window.
        """
        if self.serial_client.is_connected():
            self.serial_client.disconnect()
        self.root.destroy()

    def run(self) -> None:
        """Start GUI event loop.

        Enters the Tkinter main loop. This method blocks until the
        window is closed.
        """
        self.logger.info("Starting GUI...")
        self.root.mainloop()

    def cleanup(self) -> None:
        """Cleanup resources before exit.

        Disconnects from serial port if still connected. Called after
        the GUI event loop exits.
        """
        if self.serial_client.is_connected():
            self.serial_client.disconnect()
