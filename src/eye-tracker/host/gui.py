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
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional, Tuple

import cv2
import numpy as np
import torch
from camera import Camera

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
from eye_tracker import EyeTracker
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
        self.eye_tracker: Optional[EyeTracker] = None

        # Calibration state
        self._calibration_cap: Optional[cv2.VideoCapture] = None
        self._calibration_window: Optional[tk.Toplevel] = None
        self._calibration_canvas: Optional[tk.Canvas] = None
        self._calibration_points: list[tuple[int, int]] = []
        self._calibration_index: int = 0

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
        row = self.build_eye_tracker_section(main_frame, row)
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

    def build_eye_tracker_section(self, parent: ttk.Frame, start_row: int) -> int:
        """
        Build eye tracker control section.

        Args:
            parent: Parent frame
            start_row: Starting row number

        Returns:
            Next available row number
        """
        # Eye tracker frame
        eye_tracker_frame = ttk.LabelFrame(parent, text="Eye Tracker", padding=PADDING)
        eye_tracker_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, PADDING))

        # Configure grid
        for i in range(5):
            eye_tracker_frame.columnconfigure(i, weight=1)

        # Row 0: Control buttons
        # Start button
        ttk.Button(
            eye_tracker_frame,
            text="Start Eye Tracking",
            command=self.start_eye_tracking,
            width=BUTTON_WIDTH
        ).grid(row=0, column=0, padx=5, pady=5)

        # Stop button
        ttk.Button(
            eye_tracker_frame,
            text="Stop Eye Tracking",
            command=self.stop_eye_tracking,
            width=BUTTON_WIDTH
        ).grid(row=0, column=1, padx=5, pady=5)

        # Calibration button
        ttk.Button(
            eye_tracker_frame,
            text="Start Calibration",
            command=self.start_calibration,
            width=BUTTON_WIDTH
        ).grid(row=0, column=2, padx=5, pady=5)

        # Row 1: Gaze Vector inputs
        ttk.Label(eye_tracker_frame, text="Gaze Vector:").grid(row=1, column=0, sticky=tk.W, padx=(5, 5), pady=(10, 5))

        self.gaze_pitch_var = tk.StringVar()
        pitch_entry = ttk.Entry(eye_tracker_frame, textvariable=self.gaze_pitch_var, width=10)
        pitch_entry.grid(row=1, column=1, sticky=tk.W, padx=(0, 5), pady=(10, 5))
        ttk.Label(eye_tracker_frame, text="Pitch", font=('TkDefaultFont', 8)).grid(row=1, column=2, sticky=tk.W, padx=(0, 5), pady=(10, 5))

        self.gaze_yaw_var = tk.StringVar()
        yaw_entry = ttk.Entry(eye_tracker_frame, textvariable=self.gaze_yaw_var, width=10)
        yaw_entry.grid(row=1, column=3, sticky=tk.W, padx=(0, 5), pady=(10, 5))
        ttk.Label(eye_tracker_frame, text="Yaw", font=('TkDefaultFont', 8)).grid(row=1, column=4, sticky=tk.W, padx=(0, 5), pady=(10, 5))

        # Row 2: Gaze Origin inputs
        ttk.Label(eye_tracker_frame, text="Gaze Origin:").grid(row=2, column=0, sticky=tk.W, padx=(5, 5), pady=5)

        self.gaze_origin_x_var = tk.StringVar()
        origin_x_entry = ttk.Entry(eye_tracker_frame, textvariable=self.gaze_origin_x_var, width=10)
        origin_x_entry.grid(row=2, column=1, sticky=tk.W, padx=(0, 5), pady=5)
        ttk.Label(eye_tracker_frame, text="X", font=('TkDefaultFont', 8)).grid(row=2, column=2, sticky=tk.W, padx=(0, 5), pady=5)

        self.gaze_origin_y_var = tk.StringVar()
        origin_y_entry = ttk.Entry(eye_tracker_frame, textvariable=self.gaze_origin_y_var, width=10)
        origin_y_entry.grid(row=2, column=3, sticky=tk.W, padx=(0, 5), pady=5)
        ttk.Label(eye_tracker_frame, text="Y", font=('TkDefaultFont', 8)).grid(row=2, column=4, sticky=tk.W, padx=(0, 5), pady=5)

        # Row 3: Simulate button
        ttk.Button(
            eye_tracker_frame,
            text="Simulate",
            command=self._simulate_gaze,
            width=BUTTON_WIDTH
        ).grid(row=3, column=0, columnspan=5, padx=5, pady=(10, 5))

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

    def start_eye_tracking(self) -> None:
        # Initialize eye tracker if not already done
        if self.eye_tracker is None:
            try:
                self.eye_tracker = EyeTracker()
                self.logger.info("Eye tracker initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize eye tracker: {e}")
                messagebox.showerror(
                    "Error",
                    f"Failed to initialize eye tracker: {e}"
                )
                return

        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            self.logger.error("Failed to open webcam")
            messagebox.showerror("Error", "Failed to open webcam")
            return

        self.camera = Camera(cap, 30)
        self.camera.register_callback(self._process_frame)
        self.camera.start()
        self.logger.info("Eye tracking started")

    def _process_frame(self, frame) -> None:
        """Process a single frame from the camera for eye tracking.

        Args:
            frame: Captured video frame
        """
        self.logger.debug(f"here")
        if self.eye_tracker is None:
            return
        self.logger.debug(f"here1")

        result = self.eye_tracker.get_gaze_vector(frame)

        self.logger.debug(f"here2")

        if result is not None:
            gaze_vector, gaze_origin = result
            x, y = self.eye_tracker.predict_screen_position(gaze_vector, gaze_origin)
            # Get screen dimensions
            screen_width = self.screen_width
            screen_height = self.screen_height
            x = int((x/ screen_width) * 32767)
            x = min(max(x, 0), 32767)
            y = int((y /screen_height) * 32767)
            y = min(max(y, 0), 32767)
            self.set_coordinates(x, y)
            self.logger.info(f"Gaze vector: {gaze_vector} with origin: {gaze_origin} mapped to ({x}, {y})")
            self.serial_client.move(x, y)
        else:
            self.logger.debug("No face detected in frame")

    def _simulate_gaze(self) -> None:
        """Simulate gaze input using manual gaze vector and origin values.

        Reads pitch, yaw, and gaze origin (x, y) from GUI input fields,
        constructs the gaze vector tensor and origin array, then predicts
        the screen position and sends movement command.
        """
        # Check if eye tracker is initialized and calibrated
        if self.eye_tracker is None:
            messagebox.showerror(
                "Error",
                "Eye tracker not initialized. Please run calibration first."
            )
            return

        try:
            # Parse input values
            pitch = float(self.gaze_pitch_var.get())
            yaw = float(self.gaze_yaw_var.get())
            origin_x = float(self.gaze_origin_x_var.get())
            origin_y = float(self.gaze_origin_y_var.get())

            # Create gaze_vector tensor (1, 2) from [pitch, yaw]
            gaze_vector = torch.tensor([[pitch, yaw]], dtype=torch.float32)

            # Create gaze_origin numpy array (2,) from [x, y]
            gaze_origin = np.array([origin_x, origin_y], dtype=np.float32)

            # Use same logic as _process_frame (lines 652-664)
            x, y = self.eye_tracker.predict_screen_position(gaze_vector, gaze_origin)

            # Get screen dimensions
            screen_width = self.screen_width
            screen_height = self.screen_height

            # Convert to digitizer coordinates (0-32767)
            x = int((x / screen_width) * 32767)
            x = min(max(x, 0), 32767)
            y = int((y / screen_height) * 32767)
            y = min(max(y, 0), 32767)

            # Update GUI and send command
            self.set_coordinates(x, y)
            self.logger.info(
                f"Simulated gaze vector: {gaze_vector} with origin: {gaze_origin} "
                f"mapped to ({x}, {y})"
            )
            self.serial_client.move(x, y)

        except ValueError as e:
            messagebox.showerror(
                "Error",
                f"Invalid input values. All fields must be valid numbers.\n\n{e}"
            )
            self.logger.error(f"Failed to parse gaze simulation inputs: {e}")
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to simulate gaze: {e}"
            )
            self.logger.error(f"Error in gaze simulation: {e}")

    def stop_eye_tracking(self) -> None:
        self.camera.stop()
        self.logger.info("Eye tracking stopped")

    def start_calibration(self) -> None:
        """Start eye tracker calibration process.

        Opens fullscreen calibration window and guides user through
        9-point calibration grid.
        """
        # Initialize eye tracker if not already done
        if self.eye_tracker is None:
            try:
                self.eye_tracker = EyeTracker()
                self.logger.info("Eye tracker initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize eye tracker: {e}")
                messagebox.showerror(
                    "Error",
                    f"Failed to initialize eye tracker: {e}"
                )
                return

        # Open webcam
        self._calibration_cap = cv2.VideoCapture(0)
        if not self._calibration_cap.isOpened():
            self.logger.error("Failed to open webcam")
            messagebox.showerror("Error", "Failed to open webcam")
            return

        # Clear previous calibration data
        self.eye_tracker.clear_calibration()

        # Create debug output directory for this calibration session
        self._calibration_debug_dir = Path(__file__).parent / "calibration_debug" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self._calibration_debug_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Saving calibration debug images to {self._calibration_debug_dir}")

        # Create fullscreen calibration window
        self._calibration_window = tk.Toplevel(self.root)
        self._calibration_window.attributes('-fullscreen', True)
        self._calibration_window.configure(background='black')

        # Get screen dimensions
        screen_width = self._calibration_window.winfo_screenwidth()
        screen_height = self._calibration_window.winfo_screenheight()

        self.screen_width = screen_width
        self.screen_height = screen_height

        # Create canvas
        self._calibration_canvas = tk.Canvas(
            self._calibration_window,
            width=screen_width,
            height=screen_height,
            background='black',
            highlightthickness=0
        )
        self._calibration_canvas.pack(fill=tk.BOTH, expand=True)

        # Bind escape key to cancel
        self._calibration_window.bind('<Escape>', lambda _: self._cancel_calibration())

        # Define 25 calibration points (5x5 grid with 10% margin)
        # Positions at 10%, 30%, 50%, 70%, 90% of screen width/height
        x_positions = [
            int(screen_width * 0.1),   # 10%
            int(screen_width * 0.3),   # 30%
            int(screen_width * 0.5),   # 50%
            int(screen_width * 0.7),   # 70%
            int(screen_width * 0.9),   # 90%
        ]
        y_positions = [
            int(screen_height * 0.1),  # 10%
            int(screen_height * 0.3),  # 30%
            int(screen_height * 0.5),  # 50%
            int(screen_height * 0.7),  # 70%
            int(screen_height * 0.9),  # 90%
        ]

        self._calibration_points = [
            (x, y) for y in y_positions for x in x_positions
        ]

        self._calibration_index = 0

        # Start calibration after short delay
        self._calibration_window.after(500, self._show_next_calibration_point)
        self.logger.info("Calibration started")

    def _show_next_calibration_point(self) -> None:
        """Display next calibration point or finish if complete."""
        if self._calibration_index >= len(self._calibration_points):
            self._finish_calibration()
            return

        # Clear canvas
        self._calibration_canvas.delete('all')

        # Get current point
        point_x, point_y = self._calibration_points[self._calibration_index]

        # Draw outer circle (white)
        radius = 20
        self._calibration_canvas.create_oval(
            point_x - radius, point_y - radius,
            point_x + radius, point_y + radius,
            fill='white', outline=''
        )

        # Draw inner dot (red) for precise fixation
        inner_radius = 5
        self._calibration_canvas.create_oval(
            point_x - inner_radius, point_y - inner_radius,
            point_x + inner_radius, point_y + inner_radius,
            fill='red', outline=''
        )

        self.logger.debug(
            f"Showing calibration point {self._calibration_index + 1}/"
            f"{len(self._calibration_points)} at ({point_x}, {point_y})"
        )

        # Schedule frame capture after user looks at point
        self._calibration_window.after(700, self._capture_calibration_frame)

    def _capture_calibration_frame(self) -> None:
        """Capture frame and extract gaze vector for current calibration point."""
        ret, frame = self._calibration_cap.read()
        frame = frame[:,:,::-1]
        frame = cv2.flip(frame, 1)

        if ret:
            # Get gaze vector and origin from current frame
            result = self.eye_tracker.get_gaze_vector(frame)

            if result is not None:
                gaze_vector, gaze_origin = result
                # Add calibration point
                screen_point = self._calibration_points[self._calibration_index]
                self.eye_tracker.add_calibration_point(gaze_vector, gaze_origin, screen_point)
                self.logger.info(
                    f"Captured calibration point {self._calibration_index + 1}: "
                    f"screen={screen_point}"
                )

                # Save annotated debug image
                debug_frame = frame.copy()

                # Convert gaze_vector to numpy for calculations
                gaze_np = gaze_vector.cpu().numpy()

                display = cv2.circle(debug_frame, gaze_origin, 3, (0, 255, 0), -1)            
                display = self.draw_gaze(debug_frame, gaze_origin, gaze_vector, color=(255,0,0), thickness=2)

                # Add text overlay with calibration info
                text = f"Point {self._calibration_index + 1}: Target=({screen_point[0]}, {screen_point[1]})"
                text2 = f"Gaze vector: ({gaze_np[0]:.2f}, {gaze_np[1]:.2f}), Gaze origin: ({gaze_origin[0]}, {gaze_origin[1]})"
                cv2.putText(debug_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                           0.7, (255, 0, 0), 2)
                cv2.putText(debug_frame, text2, (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                           0.7, (255, 0, 0), 2)

                # Convert RGB back to BGR for saving
                debug_frame_bgr = debug_frame[:, :, ::-1]

                # Save debug image
                filename = self._calibration_debug_dir / f"point_{self._calibration_index + 1:02d}.png"
                cv2.imwrite(str(filename), debug_frame_bgr)
                self.logger.debug(f"Saved debug image: {filename}")
            else:
                self.logger.warning(
                    f"No face detected for calibration point "
                    f"{self._calibration_index + 1}"
                )

                # Save frame with "No face detected" message
                debug_frame = frame.copy()
                text = f"Point {self._calibration_index + 1}: No face detected"
                cv2.putText(debug_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                           0.7, (0, 0, 255), 2)

                # Convert RGB back to BGR for saving
                debug_frame_bgr = debug_frame[:, :, ::-1]

                # Save debug image
                filename = self._calibration_debug_dir / f"point_{self._calibration_index + 1:02d}_no_face.png"
                cv2.imwrite(str(filename), debug_frame_bgr)
                self.logger.debug(f"Saved debug image (no face): {filename}")
        else:
            self.logger.error("Failed to read frame from webcam")

        # Move to next point
        self._calibration_index += 1

        # Show next point after short delay
        self._calibration_window.after(300, self._show_next_calibration_point)

    def _finish_calibration(self) -> None:
        """Complete calibration process and compute mapping."""
        # Release webcam
        if self._calibration_cap is not None:
            self._calibration_cap.release()
            self._calibration_cap = None

        # Destroy calibration window
        if self._calibration_window is not None:
            self._calibration_window.destroy()
            self._calibration_window = None

        # Compute calibration
        try:
            self.eye_tracker.calibrate()
            self.logger.info("Calibration completed successfully")
            messagebox.showinfo(
                "Calibration Complete",
                "Eye tracker calibration completed successfully!\n"
                "You can now start eye tracking."
            )
        except ValueError as e:
            self.logger.error(f"Calibration failed: {e}")
            messagebox.showwarning(
                "Calibration Failed",
                f"Not enough calibration points were captured.\n\n"
                f"Some points may have missed face detection.\n"
                f"Please try again and ensure your face is clearly visible.\n\n"
                f"Error: {e}"
            )

    def _cancel_calibration(self) -> None:
        """Cancel calibration process."""
        # Release webcam
        if self._calibration_cap is not None:
            self._calibration_cap.release()
            self._calibration_cap = None

        # Destroy calibration window
        if self._calibration_window is not None:
            self._calibration_window.destroy()
            self._calibration_window = None

        self.logger.info("Calibration cancelled")

    def on_closing(self) -> None:
        """Handle window close event.

        Called when the user closes the window. Disconnects from serial
        port if connected, cleans up camera resources, and destroys the
        Tkinter window.
        """
        # Clean up calibration resources if active
        if self._calibration_cap is not None:
            self._calibration_cap.release()
        if self._calibration_window is not None:
            self._calibration_window.destroy()

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

    def draw_gaze(self, image_in, eye_pos, pitchyaw, length=200, thickness=1, color=(0, 0, 255)):
        """Draw gaze angle on given image with a given eye positions."""
        image_out = image_in
        if len(image_out.shape) == 2 or image_out.shape[2] == 1:
            image_out = cv2.cvtColor(image_out, cv2.COLOR_GRAY2BGR)
            
        dx = -length * np.sin(pitchyaw[1])
        dy = -length * np.sin(pitchyaw[0])
        cv2.arrowedLine(image_out, tuple(np.round(eye_pos).astype(np.int32)),
                    tuple(np.round([eye_pos[0] + dx, eye_pos[1] + dy]).astype(int)), color,
                    thickness, cv2.LINE_AA, tipLength=0.5)
        return image_out
