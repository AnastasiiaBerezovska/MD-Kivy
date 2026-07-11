#!/bin/bash
# Launch script for wired Arduino connection (USB)

# Configure wired Arduino connection
export ARDUINO_MODE=serial
export ARDUINO_PORT=/dev/ttyACM0    # Change to /dev/ttyUSB0 if needed
export ARDUINO_BAUD=9600            # Change if your Arduino uses different baud rate

echo "Connecting to wired Arduino at $ARDUINO_PORT @ $ARDUINO_BAUD baud"
python main.py
