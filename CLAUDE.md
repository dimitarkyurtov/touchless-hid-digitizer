# CLAUDE.md - Project Context for AI Development

This file provides context about the Touchless HID Digitizer project for AI assistants (Claude) working on this codebase.

## Project Vision

**End Goal**: Create a touchless computer interaction system using eye tracking and hand gestures that functions as a standard USB HID digitizer device.

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    HOST COMPUTER                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Host Application (Python)                               │  │
│  │  ┌────────────────┐         ┌──────────────────────┐    │  │
│  │  │ Camera Input   │────────▶│  Eye Tracking        │    │  │
│  │  │ (Webcam/USB)   │         │  (OpenCV/MediaPipe)  │    │  │
│  │  └────────────────┘         └──────────┬───────────┘    │  │
│  │                                        │                 │  │
│  │                               X,Y Coordinates            │  │
│  │                                        │                 │  │
│  │  ┌─────────────────────────────────────▼──────────────┐ │  │
│  │  │  Serial Protocol Client                            │ │  │
│  │  │  - Send MOVE commands with eye-tracked coordinates│ │  │
│  │  │  - GUI for calibration & monitoring               │ │  │
│  │  └─────────────────────────┬──────────────────────────┘ │  │
│  └────────────────────────────┼──────────────────────────────┘  │
│                               │ USB Serial (CDC ACM)            │
└───────────────────────────────┼─────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                               │                                 │
│  ┌────────────────────────────▼──────────────────────────────┐  │
│  │  HID Digitizer Device (Raspberry Pi)                     │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │  Serial Listener                                    │ │  │
│  │  │  - Receives MOVE/CLICK commands from host          │ │  │
│  │  └─────────────────────┬───────────────────────────────┘ │  │
│  │                        │                                  │  │
│  │  ┌─────────────────────▼───────────────────────────────┐ │  │
│  │  │  Command Processor                                  │ │  │
│  │  │  - Merges eye position + gesture commands          │ │  │
│  │  └─────────────────────┬───────────────────────────────┘ │  │
│  │                        │                                  │  │
│  │  ┌─────────────────────▼───────────────────────────────┐ │  │
│  │  │  HID Controller                                     │ │  │
│  │  │  - Generates USB HID reports                       │ │  │
│  │  │  - Sends to /dev/hidg0                             │ │  │
│  │  └─────────────────────┬───────────────────────────────┘ │  │
│  │                        │                                  │  │
│  │  ┌─────────────────────┴───────────────────────────────┐ │  │
│  │  │  Camera Input (Optional)                            │ │  │
│  │  │  ┌───────────────┐      ┌─────────────────────────┐│ │  │
│  │  │  │ Pi Camera or  │─────▶│  Hand Gesture Detection ││ │  │
│  │  │  │ USB Camera    │      │  (OpenCV/MediaPipe)     ││ │  │
│  │  │  └───────────────┘      └──────────┬──────────────┘│ │  │
│  │  │                                    │                │ │  │
│  │  │                           Click/Command Events      │ │  │
│  │  │                                    │                │ │  │
│  │  │                                    ▼                │ │  │
│  │  │                         Command Processor           │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               │ USB HID Reports                 │
│                    RASPBERRY PI / CUSTOM HARDWARE               │
└───────────────────────────────┼─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                    HOST OPERATING SYSTEM                        │
│                    - Receives HID reports                       │
│                    - Moves cursor based on coordinates          │
│                    - Processes click events                     │
└─────────────────────────────────────────────────────────────────┘
```

## Current Implementation Status (v1.0 - Basic Infrastructure)

### ✅ Completed Components

1. **Common Protocol Library** (`common/`)
   - ASCII-based serial protocol (MOVE, CLICK, RELEASE)
   - Command parsing and validation
   - Shared between host and digitizer
   - Coordinate range: 0-32767 (USB HID standard)

2. **HID Digitizer Device** (`digitizer/`)
   - USB gadget configuration (composite HID + CDC ACM)
   - Standard USB HID Digitizer protocol implementation
   - Serial command listener
   - HID report generation (8-byte format)
   - Systemd services for auto-start
   - Currently: Receives commands via serial, forwards to HID

3. **Host Application** (`host/`)
   - Tkinter GUI for manual control
   - Serial client for communication
   - Manual coordinate input
   - Currently: User manually enters coordinates

4. **Documentation**
   - Complete setup guides for both components
   - Protocol specification
   - Troubleshooting guides

### 🔄 Current Data Flow

```
User Input (GUI) → Serial Command → Digitizer → HID Report → OS Cursor Movement
```

## Future Development Roadmap

### Phase 2: Eye Tracking Integration (Host Side)

**Goal**: Replace manual coordinate input with real-time eye tracking.

**Components to Add**:

1. **Eye Tracking Module** (`host/eye_tracker.py`)
   - Use MediaPipe Face Mesh or OpenCV eye tracking
   - Detect gaze direction from webcam
   - Convert gaze to screen coordinates
   - Calibration system for user-specific eye tracking
   - Smoothing/filtering for stable cursor movement

2. **Camera Manager** (`host/camera_manager.py`)
   - Webcam capture (OpenCV)
   - Frame preprocessing
   - FPS management
   - Multi-camera support

3. **Calibration System** (`host/calibration.py`)
   - 9-point or 13-point calibration
   - User looks at target points
   - Build mapping from eye features to screen coordinates
   - Save/load calibration profiles

4. **Modified Host Application**
   - Real-time video display
   - Continuous eye position streaming
   - Calibration mode UI
   - Eye tracking confidence indicators
   - Toggle between manual and eye-tracking modes

**Key Technical Considerations**:
- Eye tracking runs at 30-60 FPS
- Coordinate smoothing to reduce jitter
- Latency minimization (target: <50ms end-to-end)
- Calibration persistence
- Handle lighting conditions

**Dependencies to Add**:
```
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
```

### Phase 3: Hand Gesture Recognition (Digitizer Side)

**Goal**: Detect hand gestures to trigger click events and commands.

**Components to Add**:

1. **Gesture Recognition Module** (`digitizer/gesture_recognizer.py`)
   - Use MediaPipe Hands for hand tracking
   - Detect predefined gestures:
     - Pinch → Left click
     - Two-finger pinch → Right click
     - Closed fist → Drag start
     - Open hand → Drag end
     - Peace sign → Double click
     - Custom gestures for other commands
   - Gesture state machine to prevent false triggers

2. **Camera Manager** (`digitizer/camera_manager.py`)
   - Pi Camera or USB camera support
   - Frame capture at 30 FPS
   - Efficient processing on Raspberry Pi

3. **Command Generator** (`digitizer/command_generator.py`)
   - Convert gestures to HID commands
   - Merge gesture commands with position from host
   - Priority handling (gesture overrides if needed)
   - Debouncing for gesture stability

4. **Modified Digitizer Service**
   - Run gesture recognition in parallel with serial listener
   - Thread/process management for camera + serial
   - Coordinate merging: position from host, clicks from gestures
   - Performance optimization for Raspberry Pi

**Key Technical Considerations**:
- Gesture detection runs on Raspberry Pi (limited CPU)
- May need to use TensorFlow Lite for efficiency
- Gesture detection latency (target: <100ms)
- False positive prevention
- Hand presence detection (don't process when no hand visible)

**Dependencies to Add**:
```
opencv-python>=4.8.0  # or opencv-python-headless for Pi
mediapipe>=0.10.0
numpy>=1.24.0
```

### Phase 4: Advanced Features

1. **Adaptive Smoothing**
   - Kalman filtering for eye position
   - Velocity-based smoothing
   - Adaptive gain based on target distance

2. **Gaze Zones**
   - Different sensitivity in different screen areas
   - Larger targets easier to hit (Fitts's law)
   - Edge snapping for screen boundaries

3. **Dwell Click**
   - Click by dwelling on target for configurable time
   - Alternative to gesture-based clicking
   - Visual feedback for dwell timer

4. **Gesture Customization**
   - User-defined gestures
   - Gesture training system
   - Per-application gesture profiles

5. **Performance Monitoring**
   - Latency measurements
   - FPS tracking
   - Dropped frame detection
   - Debug visualization overlays

6. **Accessibility Features**
   - Eye tracking for users with limited mobility
   - One-handed gesture operation
   - Voice command integration
   - Configurable sensitivity and speed

## Architecture Decisions

### Why Split Processing Between Host and Digitizer?

**Current Design**: Eye tracking on host, gestures on digitizer

**Rationale**:
1. **Eye tracking needs high-res webcam**: Typically on host computer
2. **Hand gestures can use Pi Camera**: Mounted near user's hands
3. **Separation of concerns**: Eye position vs. click/command events
4. **USB HID protocol**: Naturally separates position and button states
5. **Modularity**: Can use eye-only, gesture-only, or both

**Alternative Considered**: All processing on host
- Would require sending gesture commands to digitizer
- More complex protocol
- Harder to adapt to different hardware setups

### Protocol Design Considerations

**Current Protocol**: Simple ASCII commands (MOVE x y, CLICK button)

**For Eye Tracking**:
- Need high-frequency position updates (30-60 Hz)
- Current protocol adequate but may need optimization
- Consider binary protocol for reduced bandwidth
- Rate limiting to avoid overwhelming serial buffer

**For Gestures**:
- Gesture events are low frequency (1-5 Hz)
- Current protocol works well
- May add new commands: DRAG_START, DRAG_END, DOUBLE_CLICK, etc.

### Coordinate Systems

**Multiple coordinate spaces to manage**:

1. **Camera Space** (Eye Tracking)
   - Webcam resolution (e.g., 640×480)
   - Eye position in normalized coordinates (0.0-1.0)

2. **Screen Space** (Calibration)
   - Physical screen pixels (e.g., 1920×1080)
   - Calibration maps eye position to screen

3. **Digitizer Space** (USB HID)
   - Standard: 0-32767 for both X and Y
   - OS maps to actual screen resolution

**Conversion Pipeline**:
```
Eye Features → Calibration Model → Screen Pixels → Digitizer Coords → OS Cursor
```

## File Organization for Future Development

### Suggested Structure After Phase 2 & 3:

```
touchless-hid-digitizer/
├── README.md
├── CLAUDE.md                         # This file
├── LICENSE
│
├── common/                           # Shared protocol & utilities
│   ├── __init__.py
│   ├── protocol.py                   # Extended with new commands
│   ├── coordinate_utils.py           # NEW: Coordinate conversions
│   └── README.md
│
├── digitizer/                        # Device side (Raspberry Pi)
│   ├── README.md
│   ├── config.py                     # Add gesture config
│   ├── main.py                       # Modified: gesture integration
│   ├── hid_controller.py            # Unchanged
│   ├── serial_listener.py           # Unchanged
│   ├── camera_manager.py            # NEW: Camera handling
│   ├── gesture_recognizer.py        # NEW: Hand gesture detection
│   ├── command_generator.py         # NEW: Gesture → HID commands
│   ├── setup-usb-gadget.sh          # Unchanged
│   ├── requirements.txt             # Add CV dependencies
│   └── [systemd services]
│
└── host/                            # Host application (computer)
    ├── README.md
    ├── config.py                     # Add eye tracking config
    ├── main.py                       # Modified: eye tracking mode
    ├── gui.py                        # Modified: add calibration UI
    ├── serial_client.py             # Unchanged
    ├── camera_manager.py            # NEW: Webcam handling
    ├── eye_tracker.py               # NEW: Eye tracking core
    ├── calibration.py               # NEW: Calibration system
    ├── smoothing.py                 # NEW: Position smoothing
    └── requirements.txt             # Add CV dependencies
```

## Key Technologies & Libraries

### Computer Vision

- **MediaPipe**: Fast, accurate face/hand tracking
  - Face Mesh for eye tracking
  - Hands for gesture recognition
  - Optimized for real-time performance
  - Cross-platform (including Raspberry Pi with lite version)

- **OpenCV**: Camera I/O, image preprocessing
  - VideoCapture for camera access
  - Basic image operations
  - Drawing overlays for debugging

### Alternative Approaches

- **PyGaze/OpenGaze**: Specialized eye tracking libraries
- **Dlib**: Face landmark detection (heavier than MediaPipe)
- **TensorFlow Lite**: Custom gesture models for Pi efficiency

## Development Guidelines

### When Adding Eye Tracking

1. **Start with simple gaze detection**: Use MediaPipe Face Mesh iris landmarks
2. **Implement smoothing early**: Raw eye tracking is jittery
3. **Calibration is essential**: User-specific mapping required
4. **Test with different users**: Eye tracking varies significantly
5. **Performance target**: 30 FPS minimum, 60 FPS ideal
6. **Fallback mode**: Keep manual control option

### When Adding Gesture Recognition

1. **Define clear gestures**: Distinct, easy to perform
2. **Implement gesture FSM**: Prevent partial gesture detection
3. **Debouncing critical**: Avoid double-triggers
4. **Pi performance**: Profile and optimize for limited CPU
5. **Visual feedback**: Show detected hands/gestures for debugging
6. **Gesture timeout**: Reset if gesture held too long

### Performance Optimization

- **Profile first**: Measure before optimizing
- **Parallel processing**: Use threading/multiprocessing appropriately
- **Frame skipping**: Process every Nth frame if needed
- **ROI processing**: Only process relevant image regions
- **Model optimization**: Use quantized models on Raspberry Pi

## Testing Considerations

### Eye Tracking Testing

- Multiple users with different eye characteristics
- Various lighting conditions (bright, dim, backlit)
- Different screen sizes and resolutions
- Glasses vs. no glasses
- Calibration accuracy measurement
- Cursor stability metrics

### Gesture Recognition Testing

- Different hand sizes
- Various skin tones (ensure fair model)
- Different distances from camera
- Partial hand visibility
- Gesture false positive rate
- Gesture recognition latency

### Integration Testing

- End-to-end latency measurement
- Simultaneous eye + gesture operation
- Error recovery (camera disconnection, etc.)
- Long-running stability
- Resource usage monitoring

## Common Pitfalls & Solutions

### Eye Tracking

**Pitfall**: Jittery cursor movement
- **Solution**: Implement Kalman filter or moving average smoothing

**Pitfall**: Poor calibration accuracy
- **Solution**: More calibration points, per-user profiles

**Pitfall**: Lost tracking when user moves
- **Solution**: Re-calibration prompts, automatic drift correction

### Gesture Recognition

**Pitfall**: False positives
- **Solution**: Gesture state machine, confidence thresholds

**Pitfall**: Raspberry Pi too slow
- **Solution**: Lower resolution, frame skipping, TensorFlow Lite

**Pitfall**: Gesture conflicts with eye movement
- **Solution**: Clear gesture definitions, hand presence detection

### System Integration

**Pitfall**: High latency
- **Solution**: Profile pipeline, reduce buffering, optimize critical path

**Pitfall**: USB serial buffer overflow
- **Solution**: Rate limiting, binary protocol, larger buffers

**Pitfall**: Coordinate misalignment
- **Solution**: Careful coordinate space management, debugging overlays

## Environment Setup for Development

### Host Development

```bash
# Install dependencies
pip3 install opencv-python mediapipe numpy

# Test webcam
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Webcam OK' if cap.isOpened() else 'Webcam Failed')"

# Test MediaPipe
python3 -c "import mediapipe as mp; print('MediaPipe OK')"
```

### Digitizer Development (Raspberry Pi)

```bash
# Install dependencies (lightweight versions for Pi)
pip3 install opencv-python-headless mediapipe numpy

# Test camera
raspistill -o test.jpg  # For Pi Camera
# or
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera Failed')"

# Check system resources
htop  # Monitor CPU/memory during camera processing
```

## Current Limitations to Address

1. **Manual coordinate input**: Replace with eye tracking
2. **No camera integration**: Add camera managers
3. **No gesture support**: Implement gesture recognition
4. **Simple protocol**: May need enhancement for high-frequency updates
5. **No calibration system**: Essential for accurate eye tracking
6. **No smoothing**: Required for stable cursor movement
7. **Single-threaded**: Need parallel processing for camera + serial

## Success Metrics

### Eye Tracking Performance

- **Accuracy**: <50 pixels error on 1920×1080 screen after calibration
- **Latency**: <50ms from eye movement to cursor movement
- **Stability**: <10 pixels jitter during steady gaze
- **Frame rate**: 30-60 FPS

### Gesture Recognition Performance

- **Accuracy**: >95% correct gesture recognition
- **False positive rate**: <5% during normal hand movement
- **Latency**: <100ms from gesture completion to action
- **Gesture set size**: 5-8 distinct, reliable gestures

### System Performance

- **End-to-end latency**: <150ms (eye movement → cursor movement)
- **Raspberry Pi CPU usage**: <70% during operation
- **USB bandwidth**: Well within CDC ACM limits (115200 baud sufficient)

## Questions for Future Development Sessions

When continuing this project, consider:

1. Should eye tracking and gesture processing run in separate processes or threads?
2. What's the optimal camera resolution for each use case?
3. Should calibration data be stored per-user or per-device?
4. What's the minimum Raspberry Pi model that can handle gesture recognition?
5. Should the protocol support binary commands for efficiency?
6. How to handle multi-monitor setups with eye tracking?
7. What accessibility features are most important to prioritize?

## Resources & References

### Eye Tracking

- MediaPipe Face Mesh: https://google.github.io/mediapipe/solutions/face_mesh
- PyGaze: http://www.pygaze.org/
- GazeTracking library: https://github.com/antoinelame/GazeTracking

### Gesture Recognition

- MediaPipe Hands: https://google.github.io/mediapipe/solutions/hands
- Hand Gesture Recognition Datasets: https://github.com/hukenovs/hagrid

### USB HID

- USB HID Usage Tables: https://www.usb.org/document-library/hid-usage-tables-13
- Linux USB Gadget: https://www.kernel.org/doc/html/latest/usb/gadget.html

### Research Papers

- Eye tracking for accessibility: Various papers on gaze-based interaction
- Hand gesture recognition: MediaPipe research, gesture taxonomy

## Development Workflow & Automation

### Python Code Writer Sub-Agent

**IMPORTANT**: This project uses a specialized Python code writer sub-agent that MUST be used for all Python code tasks.

**Automatic Usage Policy**:
- **ALWAYS** use the Task tool with `subagent_type="python-code-writer"` when writing, modifying, or refactoring Python code
- This applies to ALL Python files in the project: `host/`, `digitizer/`, and `common/` directories
- Do NOT write Python code directly - delegate to the python-code-writer sub-agent
- The sub-agent ensures code follows Python best practices, project standards, and modern Python idioms

**When to Use the Python Code Writer**:
1. Creating new Python modules or scripts
2. Modifying existing Python code
3. Refactoring Python code for better quality
4. Adding new features to Python files
5. Fixing bugs in Python code
6. Updating requirements.txt or other Python project files

**Example Usage**:
```
User: "Add eye tracking module to the host application"
Claude: [Uses Task tool with python-code-writer to implement host/eye_tracker.py]

User: "Refactor the serial client to use async I/O"
Claude: [Uses Task tool with python-code-writer to refactor host/serial_client.py]
```

**Benefits**:
- Consistent code quality across the project
- Adherence to Python standards (PEP 8, type hints, docstrings)
- Modern Python patterns and idioms
- Proper error handling and validation
- Optimized for the project's architecture

## Notes for Claude

- This is a computer vision + HCI project with hardware integration
- The current implementation is a **foundation** for the full vision
- Priority is **accuracy and low latency** over feature richness
- Target users include people with **limited mobility** (accessibility focus)
- Performance constraints: Raspberry Pi has limited CPU
- The system should feel **natural and responsive** to use
- **Use the python-code-writer sub-agent for ALL Python code tasks** (see Development Workflow section above)

When working on this project:
1. Consider performance implications of CV algorithms
2. Think about real-time constraints (latency matters)
3. Test error cases (camera failures, lost tracking, etc.)
4. Keep accessibility in mind
5. Document coordinate space conversions clearly
6. Profile and optimize bottlenecks
7. **ALWAYS delegate Python code tasks to the python-code-writer sub-agent**

---

**Last Updated**: 2025-12-16
**Current Version**: 1.0 (Basic Infrastructure)
**Next Milestone**: Phase 2 - Eye Tracking Integration
