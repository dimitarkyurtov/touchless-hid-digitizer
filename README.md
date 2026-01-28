# Touchless HID Digitizer

A touchless computer interaction system that uses eye tracking and hand gesture recognition to control cursor position and clicks through a standard USB HID digitizer device. The neural networks for gesture recognition are trained by hand. They detect specific gestures like pinch-to-click and other specific movements to control the host machine. The digitizer acts as proxy for the host process to send HID reports to the OS. The computation is done on the host machine. This solution is fully cross platform with no permissions required besides the camera one.

## Getting Started

To use this solution, install the digitizer code on a separate hardware device (such as a Raspberry Pi with USB OTG support) which acts as a USB HID digitizer. Then, connect it to your host computer and run the host application to start controlling the cursor. Play around with the buttons and gestures to explore the different interaction modes.
