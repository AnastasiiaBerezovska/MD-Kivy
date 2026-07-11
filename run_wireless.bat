@echo off
REM Launch script for wireless Arduino connection on Windows

REM Configure wireless Arduino connection
set ARDUINO_MODE=tcp
set ARDUINO_TCP_HOST=192.168.4.1    # Replace with my Arduino's IP address    
set ARDUINO_TCP_PORT=8888

echo Connecting to wireless Arduino at %ARDUINO_TCP_HOST%:%ARDUINO_TCP_PORT%
python main.py


# access the serial monitor data