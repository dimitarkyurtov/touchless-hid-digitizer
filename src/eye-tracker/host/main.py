#!/usr/bin/env python3
"""HID Digitizer Controller - Host Application.

This is the main entry point for the host controller GUI application.
It initializes logging, creates the Tkinter GUI, and starts the event loop.

The application provides a manual control interface for the HID digitizer,
allowing users to send move, click, and release commands over serial.

In future versions, this will be extended to support eye tracking and
automated cursor control.

Example:
    Run the application::

        python3 main.py

    Or make executable and run directly::

        chmod +x main.py
        ./main.py
"""

import logging
import sys

from config import LOG_LEVEL
from gui import HIDDigitizerGUI


def setup_logging() -> None:
    """Configure logging for the application.

    Sets up console logging to stdout with timestamp, logger name,
    log level, and message. Uses LOG_LEVEL from config.
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Main entry point for the host application.

    Initializes logging, creates the GUI application, and enters the
    Tkinter event loop. Handles keyboard interrupts and fatal errors
    gracefully.

    Exit codes:
        0: Normal exit or keyboard interrupt
        1: Fatal error occurred
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting HID Digitizer Controller application...")

        # Create and run GUI
        app = HIDDigitizerGUI()
        app.run()

        # Cleanup after GUI exits
        app.cleanup()

        logger.info("Application exited normally")

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
