# Documentation

## 1. Functionality

The Touchless HID Digitizer is a touchless computer interaction system that enables users to control cursor position and mouse clicks using eye tracking and hand gesture recognition from 2D camera images. The system functions as a standard USB HID digitizer device, making it fully cross-platform with no driver installation required.

### Core Features

#### Eye Tracking
- Real-time gaze detection using pre-trained neural networks (GazeNet or PyGaze)
- 25-point calibration system with polynomial regression for screen mapping
- Gaze vector prediction (pitch and yaw angles) with optional gaze origin tracking
- Support for face normalization and MTCNN face detection

#### Hand Gesture Recognition
- **Touch Gestures** (MediaPipe Hand Landmarker):
  - Thumb + Index finger touch → Left click
  - Thumb + Middle finger touch → Right click
  - Thumb + Ring finger touch → Media play/pause
- **Continuous Gestures** (LSTM Neural Network):
  - Thumbs Up → Next track
  - Thumbs Down → Previous track

#### HID Control
- Standard USB HID Digitizer protocol (0-32767 coordinate range)
- Consumer Control HID for media keys (Play/Pause, Next Track, Previous Track)
- Button press, release, and click operations
- Absolute cursor positioning

#### Serial Communication
- ASCII-based protocol over USB CDC ACM
- Commands: MOVE, CLICK, RELEASE, BUTTON_PRESS, BUTTON_RELEASE
- Media commands: MEDIA_PLAY_PAUSE, MEDIA_NEXT, MEDIA_PREV
- Gesture control: GESTURE_START, GESTURE_STOP

---

## 2. Architecture

The system uses a distributed architecture with two main components:

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    HOST COMPUTER                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Host Application (Python)                               │  │
│  │  ┌────────────────┐         ┌──────────────────────┐    │  │
│  │  │ Eye Tracking   │────────▶│  GazeNet / PyGaze    │    │  │
│  │  │ Camera         │         │  Neural Network      │    │  │
│  │  └────────────────┘         └──────────┬───────────┘    │  │
│  │  ┌────────────────┐         ┌──────────▼───────────┐    │  │
│  │  │ Gesture        │────────▶│  MediaPipe + LSTM    │    │  │
│  │  │ Camera         │         │  Hand Recognition    │    │  │
│  │  └────────────────┘         └──────────┬───────────┘    │  │
│  │                                        │                 │  │
│  │  ┌─────────────────────────────────────▼──────────────┐ │  │
│  │  │  Serial Protocol Client (GUI / Headless)          │ │  │
│  │  └─────────────────────────────────────┬──────────────┘ │  │
│  └────────────────────────────────────────┼──────────────────┘  │
└───────────────────────────────────────────┼─────────────────────┘
                                            │ USB Serial (CDC ACM)
┌───────────────────────────────────────────┼─────────────────────┐
│                    RASPBERRY PI                                 │
│  ┌────────────────────────────────────────▼──────────────────┐  │
│  │  HID Digitizer Device                                     │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                │  │
│  │  │ Serial Listener │──│ Command Parser  │                │  │
│  │  └─────────────────┘  └────────┬────────┘                │  │
│  │                                │                          │  │
│  │  ┌─────────────────────────────▼──────────────────────┐  │  │
│  │  │  HID Controller                                     │  │  │
│  │  │  - /dev/hidg0 (Mouse/Pointer)                      │  │  │
│  │  │  - /dev/hidg1 (Consumer Control)                   │  │  │
│  │  └─────────────────────────────┬──────────────────────┘  │  │
│  └────────────────────────────────┼──────────────────────────┘  │
└───────────────────────────────────┼─────────────────────────────┘
                                    │ USB HID Reports
┌───────────────────────────────────▼─────────────────────────────┐
│                    HOST OPERATING SYSTEM                        │
│                    - Standard HID Driver                        │
│                    - No additional software required            │
└─────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### Host Application (`src/eye-tracker/host/`)
- **main.py**: Application entry point
- **gui.py**: Tkinter-based graphical interface
- **eye_tracker.py**: Eye tracking and calibration logic
- **hand_gesture_recognizer.py**: Gesture detection using MediaPipe and LSTM
- **serial_client.py**: Serial communication with digitizer
- **camera.py**: Camera capture management
- **media_key_listener.py**: Media key event handling
- **config.py**: Host configuration settings

#### Digitizer Device (`src/eye-tracker/digitizer/`)
- **main.py**: Service entry point
- **hid_controller.py**: HID report generation and transmission
- **serial_listener.py**: Serial command reception
- **config.py**: Device configuration settings
- **setup-usb-gadget.sh**: USB gadget configuration script
- **Systemd services**: usb-gadget.service, hid-digitizer.service

#### Common Library (`src/eye-tracker/common/`)
- **protocol.py**: Serial communication protocol definitions
- **gesture_types.py**: Gesture enumeration definitions
- **camera.py**: Shared camera utilities

#### Neural Networks (`src/neural_nets/`)
- **gaze_vector/**: GazeNet model with MTCNN face detection
- **hand_landmarker/**: MediaPipe Hand Landmarker model (local copy)
- **hand_gesture_recognizer/**: LSTM model for continuous gestures

---

## 3. Used Datasets

### Eye Tracking

The GazeNet model was trained on the following datasets:
- **Mobile Face Gaze**: Trained based on [mobile-face-gaze](https://github.com/glefundes/mobile-face-gaze) project
- Modified for macOS support with custom `gazenet.py` implementation

### Hand Gesture Recognition

- **Hand Landmarker Model**: Google's official MediaPipe Hand Landmarker model (float16 version)
  - Downloaded from: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`

- **LSTM Gesture Model**: Trained following the approach from [HandGestureRecognition-using-3D-Conv-and-CNN-RNN-Stack](https://github.com/sancharee/HandGestureRecognition-using-3D-Conv-and-CNN-RNN-Stack)
  - Architecture modifications for the specific gesture set (ThumbsUp, ThumbsDown)
  - Input dimensions: 10 frames × 120×120×3 RGB
  - Direct link: https://drive.google.com/uc?id=1ehyrYBQ5rbQQe6yL4XbLWe3FMvuVUGiL

---

## 4. Technologies and Libraries

### Host Application Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| `opencv-python` | >=4.8.0 | Camera capture, image processing |
| `opencv-contrib-python` | >=4.8.0 | Additional OpenCV modules |
| `mediapipe` | >=0.10.0 | Hand landmark detection |
| `tensorflow` | >=2.16.0 | LSTM model inference |
| `torch` | latest | GazeNet neural network |
| `torchvision` | latest | Image preprocessing for PyTorch |
| `numpy` | latest | Numerical computations |
| `Pillow` | latest | Image handling |
| `pyserial` | >=3.5 | Serial communication |
| `pynput` | latest | Keyboard/mouse input simulation |
| `scikit-image` | >=0.21.0 | Image resizing for LSTM |

### Digitizer Device Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| `pyserial` | >=3.5 | Serial communication |
| `opencv-python` | 4.8.1.78 | Camera capture (optional) |
| `mediapipe` | >=0.10.0 | Hand gesture recognition (optional) |
| `numpy` | 1.26.4 | Numerical computations |
| `tensorflow` | >=2.16.0 | LSTM inference (optional) |
| `scikit-image` | >=0.21.0 | Image preprocessing (optional) |


---
