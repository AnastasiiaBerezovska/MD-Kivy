@echo off
REM Launch script for wired Arduino connection (USB) on Windows

REM Configure wired Arduino connection
set ARDUINO_MODE=serial
set ARDUINO_PORT=COM3
set ARDUINO_BAUD=9600

echo Connecting to wired Arduino at %ARDUINO_PORT% @ %ARDUINO_BAUD% baud
python main.py
