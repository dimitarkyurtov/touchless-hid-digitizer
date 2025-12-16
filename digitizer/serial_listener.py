"""Serial Listener for HID Digitizer Device.

This module handles serial communication with the host application over
USB CDC ACM (Communication Device Class - Abstract Control Model). It
receives ASCII commands, decodes them, and invokes a callback function
for processing.

The serial listener runs in a blocking loop, continuously reading lines
from the serial port and passing them to a registered callback. It handles
encoding/decoding, error recovery, and response transmission back to the host.

Example:
    Use with a callback function::

        def handle_command(cmd: str) -> None:
            print(f"Received: {cmd}")

        listener = SerialListener()
        listener.open()
        listener.listen(handle_command)  # Blocks until stopped

    Or use as a context manager::

        with SerialListener() as listener:
            listener.listen(handle_command)
"""

import logging
from typing import Callable, Optional

import serial

from config import SERIAL_BAUDRATE, SERIAL_DEVICE, SERIAL_TIMEOUT


class SerialListener:
    """Listens for commands on the USB CDC ACM serial port.

    Reads newline-terminated ASCII commands from the CDC ACM serial device
    and invokes a callback function for each received command line.

    The listener maintains a connection to the serial port and provides
    methods for sending responses back to the host. It implements the
    context manager protocol for automatic resource management.

    Attributes:
        device (str): Path to the serial device file.
        baudrate (int): Serial communication baud rate.
        timeout (float): Read timeout in seconds.
        serial (Optional[serial.Serial]): PySerial port object when open.
        running (bool): Flag indicating if listener loop is active.
        logger (logging.Logger): Logger instance for this listener.
    """

    def __init__(
        self,
        device: str = SERIAL_DEVICE,
        baudrate: int = SERIAL_BAUDRATE,
        timeout: float = SERIAL_TIMEOUT,
    ) -> None:
        """Initialize serial listener.

        Args:
            device: Serial device path. Defaults to /dev/ttyGS0
                as configured in config.SERIAL_DEVICE.
            baudrate: Serial baud rate. Defaults to 115200.
            timeout: Read timeout in seconds. Defaults to 1.0.
                Used for readline() operations.
        """
        self.device: str = device
        self.baudrate: int = baudrate
        self.timeout: float = timeout
        self.serial: Optional[serial.Serial] = None
        self.running: bool = False
        self.logger: logging.Logger = logging.getLogger(__name__)

    def open(self) -> None:
        """Open serial port for communication.

        Configures the serial port with 8 data bits, no parity, and 1 stop bit
        (8N1 configuration), which is standard for USB CDC ACM communication.

        Raises:
            serial.SerialException: If the port cannot be opened (e.g., device
                doesn't exist, insufficient permissions, or port already in use).
        """
        try:
            self.serial = serial.Serial(
                port=self.device,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self.logger.info(
                f"Opened serial port: {self.device} at {self.baudrate} baud"
            )
        except serial.SerialException as e:
            self.logger.error(f"Failed to open serial port {self.device}: {e}")
            raise

    def close(self) -> None:
        """Close serial port and release resources.

        Safe to call multiple times. Suppresses exceptions during close
        but logs errors for debugging.
        """
        if self.serial:
            try:
                self.serial.close()
                self.logger.info("Closed serial port")
            except Exception as e:
                self.logger.error(f"Error closing serial port: {e}")
            finally:
                self.serial = None

    def is_open(self) -> bool:
        """Check if serial port is currently open.

        Returns:
            True if port is open and ready for I/O, False otherwise.
        """
        return self.serial is not None and self.serial.is_open

    def send_response(self, message: str) -> None:
        """Send response message back to host.

        Encodes the message as UTF-8, appends a newline terminator, and
        transmits it over the serial port. Silently fails if port is not open.

        Args:
            message: Response message text (without newline terminator).
                Typically "OK" or "ERROR <details>".

        Note:
            Errors during transmission are logged but do not raise exceptions,
            allowing the service to continue even if response delivery fails.
        """
        if not self.is_open():
            self.logger.warning("Cannot send response: serial port not open")
            return

        try:
            response = f"{message}\n".encode('utf-8')
            self.serial.write(response)
            self.serial.flush()
            self.logger.debug(f"Sent response: {message}")
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

    def listen(self, callback: Callable[[str], None]) -> None:
        """Listen for commands and invoke callback for each line.

        This is a blocking function that continuously reads from the serial
        port and invokes the callback for each received newline-terminated line.

        The listener handles decoding errors, serial port errors, and other
        exceptions gracefully, logging errors and continuing to operate when
        possible. It can be stopped by calling stop() from another thread or
        by keyboard interrupt.

        Args:
            callback: Function to call with each command line. Receives the
                command string with leading/trailing whitespace stripped and
                without the newline terminator.

        Raises:
            IOError: If serial port is not open when listen() is called.

        Note:
            This method blocks until stop() is called or a KeyboardInterrupt
            is received. It should be called after open().
        """
        if not self.is_open():
            raise IOError("Serial port not open")

        self.running = True
        self.logger.info("Starting serial listener...")

        while self.running:
            try:
                # Check if data is available before reading
                if self.serial.in_waiting > 0:
                    # Read line (blocks until newline or timeout)
                    line_bytes = self.serial.readline()

                    if line_bytes:
                        try:
                            # Decode UTF-8 and strip whitespace
                            line = line_bytes.decode('utf-8').strip()

                            if line:
                                self.logger.debug(f"Received command: {line}")
                                # Invoke callback with decoded command
                                callback(line)
                        except UnicodeDecodeError as e:
                            self.logger.error(f"Failed to decode line: {e}")
                            self.send_response("ERROR Invalid encoding")

            except serial.SerialException as e:
                self.logger.error(f"Serial error: {e}")
                # Don't break loop - error might be temporary
                continue

            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt")
                break

            except Exception as e:
                self.logger.error(f"Unexpected error in listen loop: {e}")
                # Continue listening despite unexpected errors
                continue

        self.logger.info("Serial listener stopped")

    def stop(self) -> None:
        """Stop the listening loop.

        Sets the running flag to False, causing the listen() method to exit.
        This is thread-safe and can be called from signal handlers or other
        threads.

        Note:
            The listen() loop will exit on its next iteration after stop()
            is called. There may be a delay of up to timeout seconds.
        """
        self.logger.info("Stopping serial listener...")
        self.running = False

    def __enter__(self) -> "SerialListener":
        """Context manager entry - opens the serial port.

        Returns:
            Self for use in with statements.

        Raises:
            serial.SerialException: If port cannot be opened.
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - stops listener and closes the port.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.

        Returns:
            False to propagate any exception that occurred.
        """
        self.stop()
        self.close()
        return False
