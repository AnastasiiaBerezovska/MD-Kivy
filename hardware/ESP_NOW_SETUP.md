# ESP-NOW Wireless Arduino Setup

This guide covers the wireless accelerometer setup using two ESP32 boards:

1. **Transmitter** - ESP32 with an MPU6050 accelerometer, battery-powered.
2. **Receiver** - ESP32 connected to the computer over USB.

The boards communicate with the ESP-NOW protocol; the receiver forwards the
readings to the Python app over USB serial.

## Setup

### 1. Get the receiver's MAC address

Connect the receiver ESP32 over USB and flash this sketch:

```cpp
#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  Serial.print("Receiver MAC Address: ");
  Serial.println(WiFi.macAddress());
}

void loop() {
  delay(1000);
}
```

Open the Serial Monitor at 115200 baud and copy the MAC address
(formatted like `AA:BB:CC:DD:EE:FF`).

### 2. Set the MAC address in the transmitter sketch

Open `hardware/arduino_transmitter_fixed.ino` and find:

```cpp
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
```

Replace the bytes with the receiver's MAC address. For example, for
`24:6F:28:A1:B2:C3`:

```cpp
uint8_t broadcastAddress[] = {0x24, 0x6F, 0x28, 0xA1, 0xB2, 0xC3};
```

### 3. Flash the transmitter

1. Connect the transmitter ESP32 (the one with the MPU6050) over USB.
2. Open `hardware/arduino_transmitter_fixed.ino` in the Arduino IDE.
3. Select the board (Tools -> Board -> ESP32 Arduino -> ESP32 Dev Module) and port.
4. Upload, then disconnect and power from a battery (or stay on USB for testing).

### 4. Flash the receiver

1. Connect the receiver ESP32 over USB.
2. Open `hardware/arduino_receiver_fixed.ino` and upload it the same way.
3. Leave this board connected - it stays plugged into the computer.

### 5. Test the link

Open the Serial Monitor at 9600 baud with the receiver connected, then move the
transmitter. The monitor should print lines like:

```
X = 1234 | Y = 5678 | Z = 9012
```

If those lines appear, the wireless link is working.

### 6. Run the app

```bash
cd MD-Kivy
./run_wired.sh        # Linux/Mac
```

On Windows, set the COM port in `run_wired.bat` and run it. The receiver is a
normal USB serial device, so the wired launch script is the right one - the
wireless hop happens between the two ESP32 boards.

## Data flow

```
[Transmitter ESP32 + MPU6050] --ESP-NOW--> [Receiver ESP32] --USB serial--> [Python app]
```

1. The transmitter samples the MPU6050 accelerometer.
2. It sends the readings to the receiver over ESP-NOW every 100 ms.
3. The receiver prints them to USB serial at 9600 baud.
4. The Python app parses the serial stream and feeds it into the simulation.

## Troubleshooting

**Transmitter prints "Delivery Fail"** - the MAC address is wrong or the
receiver is not powered. Re-check the address bytes, make sure the receiver is
running, and keep the boards within 10-20 meters. For a quick test you can
broadcast to all devices with `{0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}`.

**No data in the Serial Monitor** - confirm both boards were flashed
successfully and restart them. Verify the MAC address.

**The Python app reads nothing** - check the serial port (`ls /dev/ttyACM*
/dev/ttyUSB*` on Linux, Device Manager -> Ports on Windows) and confirm the
receiver's `Serial.begin` is 9600, which is the app's default baud rate. Update
the port in `run_wired.sh` / `run_wired.bat` if needed.

**Parse errors** - the receiver must print exactly
`X = 1234 | Y = 5678 | Z = 9012`. Verify the output in the Serial Monitor
before starting the app. You can also type a line in that format into the
Serial Monitor to test the parser manually.

## Configuration summary

| | Transmitter | Receiver |
|---|---|---|
| Role | Reads MPU6050, sends via ESP-NOW | Receives, prints to USB serial |
| Baud rate | 115200 (debug output only) | 9600 (must match the app) |
| Power | Battery or USB | USB (stays connected) |
| Interval | Sends every 100 ms | - |

The Python app (`mdkivy/inputs/arduino_reading.py`) auto-detects the serial
port and parses the `X = ... | Y = ... | Z = ...` format by default; no configuration
is needed on the software side.
