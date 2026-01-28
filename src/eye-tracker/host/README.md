# Host Application

This is the main application that performs all the computational work for the touchless HID digitizer system which is ran on the host machine. It uses neural networks for eye tracking and hand gesture recognition, processes webcam input in real-time, and sends HID commands to the digitizer device over a serial connection. There are 2 cameras involved, one is used for the eye tracking (attached on the top of the screen or in the laptop case the integrated one) and for the hand gestures recognition (a second camera which monitors a hand).

## Requirements

- **Python**: 3.11 to 3.13
- **Operating System**: macOS, Windows, or Linux

## Starting the Application

```bash
cd src/eye-tracker/host
pip install -r requirements.txt
python main.py
```

## How It Works

### Eye Tracking

The eye tracker uses a pre-trained neural network (GazeNet or PyGaze, configurable in `config.py`) to estimate gaze direction from webcam frames. The neural network analyzes facial features and eye positions to output a gaze vector consisting of pitch and yaw angles.

### Calibration with Polynomial Regression

Since the relationship between gaze angles and screen position varies per user and screen (due to head position, screen distance, etc.), the system requires calibration. During calibration:

1. A 25-point grid (5x5) is displayed across the screen
2. You look at each point while the system captures your gaze vector and origin
3. A 2nd degree polynomial regression model is trained on-the-fly using these data points
4. The model learns to map gaze features (pitch, yaw, origin x, origin y, and their polynomial combinations) to screen X and Y coordinates
5. After calibration, the trained coefficients are used in real-time to predict where you're looking on the screen

The polynomial features include terms like `pitch`, `yaw`, `pitch²`, `yaw²`, `pitch*yaw`, and cross-terms with the gaze origin, allowing the model to capture non-linear relationships.

### Hand Gesture Recognition

The hand gesture recognizer uses two neural networks:

1. **MediaPipe Hand Landmarker**: Detects hand landmarks in real-time and measures distances between thumb and finger tips to detect touch gestures:
   - Thumb + Index finger touch = Left click
   - Thumb + Middle finger touch = Right click
   - Thumb + Ring finger touch = Media play/pause

2. **LSTM Neural Network**: Processes sequences of frames to recognize continuous gestures:
   - Thumbs Up = Next track
   - Thumbs Down = Previous track

## GUI Reference

### Serial Port Connection

| Element | Description |
|---------|-------------|
| **Port** | Dropdown to select the serial port connected to the digitizer device |
| **Refresh** | Rescans for available serial ports |
| **Connect/Disconnect** | Toggles the connection to the selected port |
| **Status** | Shows current connection state (green = connected, red = disconnected) |

### Coordinates

| Element | Description |
|---------|-------------|
| **X / Y** | Manual coordinate input fields (range: 0-32767) |
| **Center** | Sets coordinates to screen center (16384, 16384) |
| **Top-Left** | Sets coordinates to (0, 0) |
| **Bottom-Right** | Sets coordinates to (32767, 32767) |

### Actions

| Button | Description |
|--------|-------------|
| **Move** | Moves cursor to the coordinates in X/Y fields |
| **Left Click** | Sends a left mouse click |
| **Right Click** | Sends a right mouse click |
| **Move + Left Click** | Moves to coordinates then performs left click |
| **Move + Right Click** | Moves to coordinates then performs right click |
| **Release** | Releases all pressed buttons |

### Eye Tracker

| Element | Description |
|---------|-------------|
| **Start Eye Tracking** | Begins capturing webcam frames and tracking gaze |
| **Stop Eye Tracking** | Stops the eye tracking process |
| **Start Calibration** | Opens fullscreen calibration window with 25 target points |
| **Gaze Vector (Pitch/Yaw)** | Manual input fields to simulate gaze angles |
| **Gaze Origin (X/Y)** | Manual input fields to simulate gaze origin position |
| **Simulate** | Tests the calibration model with manual gaze values |

### Hand Gesture Recognition

| Element | Description |
|---------|-------------|
| **Start** | Begins capturing from the gesture camera and recognizing hand gestures |
| **Stop** | Stops gesture recognition |
| **Recent Gesture Events** | Log showing the last 5 detected gestures with timestamps |

### Information

Displays a reference for the digitizer coordinate system (0-32767 range maps to screen resolution).

## Gesture Demo

A standalone script for testing hand gesture recognition without the full GUI with extra debug information:

```bash
python gesture_demo.py
```
