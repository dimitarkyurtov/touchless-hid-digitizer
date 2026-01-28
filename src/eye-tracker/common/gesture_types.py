from enum import Enum, auto


class GestureType(Enum):
    """Enumeration of recognizable hand gestures.

    Defines all possible gesture events that can be detected by the hand
    gesture recognition system. Each enum member represents a distinct
    gesture event that triggers a specific action in the HID digitizer system.

    Button events are generated based on state changes:
    - Clicked events occur when a finger starts touching the thumb
    - Released events occur when a finger stops touching the thumb

    Attributes:
        PrimaryButtonClicked: Left mouse button press (index finger touches thumb).
        PrimaryButtonReleased: Left mouse button release (index finger leaves thumb).
        SecondaryButtonClicked: Right mouse button press (middle finger touches thumb).
        SecondaryButtonReleased: Right mouse button release (middle finger leaves thumb).
        TertiaryButtonClicked: Middle mouse button press (ring finger touches thumb).
        TertiaryButtonReleased: Middle mouse button release (ring finger leaves thumb).
        SwipeLeft: Leftward swipe gesture for navigation (future use).
        SwipeRight: Rightward swipe gesture for navigation (future use).
        ThumbsUp: Thumbs up gesture detected by LSTM model (continuous gesture).
        ThumbsDown: Thumbs down gesture detected by LSTM model (continuous gesture).

    Notes:
        - An empty list represents no gesture events
        - Multiple events can occur in a single frame
        - Continuous gestures (ThumbsUp, ThumbsDown) require temporal analysis
          over multiple frames using the LSTM neural network model
    """

    PrimaryButtonClicked = auto()
    PrimaryButtonReleased = auto()
    SecondaryButtonClicked = auto()
    SecondaryButtonReleased = auto()
    TertiaryButtonClicked = auto()
    TertiaryButtonReleased = auto()
    SwipeLeft = auto()
    SwipeRight = auto()
    ThumbsUp = auto()
    ThumbsDown = auto()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<GestureType.{self.name}>"
