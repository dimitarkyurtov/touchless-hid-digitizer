"""Media Key Listener for HID Digitizer Host Application.

This module provides a wrapper around pynput's keyboard listener to detect
media key presses (play/pause, next track, previous track) from the operating
system. The listener runs in a background daemon thread and invokes a callback
when media keys are pressed.

Classes:
    MediaKeyListener: Listens for OS media key events and invokes callbacks.

Example:
    >>> def on_media_key(key_name: str) -> None:
    ...     print(f"Media key pressed: {key_name}")
    ...
    >>> listener = MediaKeyListener(callback=on_media_key)
    >>> listener.start()
    >>> # ... wait for media key presses ...
    >>> listener.stop()
"""

import logging
from typing import Callable

from pynput import keyboard
from pynput.keyboard import Key

# Configure logging
logger = logging.getLogger(__name__)


class MediaKeyListener:
    """Listens for OS media key events and invokes a callback.

    This class wraps pynput's keyboard.Listener to specifically detect media
    control keys (play/pause, next track, previous track). When a media key
    is pressed, the registered callback is invoked with a human-readable
    string representation of the key.

    The listener runs in a background daemon thread automatically started by
    pynput, so it won't block the main thread or prevent program exit.

    Attributes:
        _callback (Callable[[str], None]): Function called when media key pressed.
        _listener (keyboard.Listener | None): The pynput keyboard listener instance.

    Args:
        callback: Function to call when a media key is pressed. Receives a
            string argument like "Play/Pause", "Next Track", or "Previous Track".

    Example:
        >>> def handle_media_key(key_name: str) -> None:
        ...     logger.info(f"Media key pressed: {key_name}")
        ...
        >>> listener = MediaKeyListener(callback=handle_media_key)
        >>> listener.start()
        >>> # Listener is now active in background thread
        >>> listener.stop()
        >>> # Listener is now stopped
    """

    # Mapping from pynput Key constants to human-readable names
    _MEDIA_KEY_NAMES = {
        Key.media_play_pause: "Play/Pause",
        Key.media_next: "Next Track",
        Key.media_previous: "Previous Track",
    }

    def __init__(self, callback: Callable[[str], None]) -> None:
        """Initialize the media key listener.

        Args:
            callback: Function to invoke when a media key is pressed. The
                function should accept a single string argument representing
                the key name (e.g., "Play/Pause", "Next Track", "Previous Track").
        """
        self._callback = callback
        self._listener: keyboard.Listener | None = None
        logger.debug("MediaKeyListener initialized")

    def _on_press(self, key: Key) -> None:
        """Internal callback for keyboard press events.

        Filters for media keys and invokes the user callback with the
        appropriate key name.

        Args:
            key: The key that was pressed (from pynput).
        """
        # Check if the pressed key is one of the media keys we care about
        if key in self._MEDIA_KEY_NAMES:
            key_name = self._MEDIA_KEY_NAMES[key]
            logger.debug(f"Media key detected: {key_name}")
            try:
                self._callback(key_name)
            except Exception as e:
                logger.error(f"Error in media key callback: {e}", exc_info=True)

    def start(self) -> None:
        """Start listening for media key events.

        Starts the pynput keyboard listener in a background daemon thread.
        The listener will continue running until stop() is called.

        If the listener is already running, this method does nothing.

        Note:
            The listener runs in a daemon thread, so it will automatically
            terminate when the main program exits.
        """
        if self._listener is not None and self._listener.is_alive():
            logger.warning("MediaKeyListener is already running")
            return

        logger.info("Starting media key listener")
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()
        logger.info("Media key listener started")

    def stop(self) -> None:
        """Stop listening for media key events.

        Stops the pynput keyboard listener and cleans up resources.

        If the listener is not running, this method does nothing.
        """
        if self._listener is None:
            logger.warning("MediaKeyListener is not running")
            return

        logger.info("Stopping media key listener")
        self._listener.stop()
        self._listener = None
        logger.info("Media key listener stopped")
