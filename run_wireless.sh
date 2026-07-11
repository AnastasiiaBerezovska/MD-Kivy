#!/bin/bash
# Launch script for wireless Arduino connection

# Configure wireless Arduino connection
export ARDUINO_MODE=tcp
export ARDUINO_TCP_HOST=192.168.4.1  # Change this to your Arduino's IP address
export ARDUINO_TCP_PORT=8888         # Change this to your Arduino's TCP port if different

echo "Connecting to wireless Arduino at $ARDUINO_TCP_HOST:$ARDUINO_TCP_PORT"
python main.py
