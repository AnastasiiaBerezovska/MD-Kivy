# Arduino Configuration Guide

This app supports both wired (USB) and wireless (TCP/Wi-Fi) Arduino connections.

## Quick Start

### For Wireless Arduino (ESP8266/ESP32):

#### Linux/Mac:
1. Find your Arduino's IP address (check your router or serial monitor)
2. Edit `run_wireless.sh` and change the IP address:
   ```bash
   export ARDUINO_TCP_HOST=192.168.1.100  # Your Arduino's IP
   ```
3. Run the wireless script:
   ```bash
   ./run_wireless.sh
   ```

#### Windows:
1. Find your Arduino's IP address (check your router or serial monitor)
2. Edit `run_wireless.bat` and change the IP address:
   ```batch
   set ARDUINO_TCP_HOST=192.168.1.100
   ```
3. Double-click `run_wireless.bat` or run in Command Prompt:
   ```cmd
   run_wireless.bat
   ```

### For Wired Arduino (USB):

#### Linux/Mac:
1. Plug in your Arduino via USB
2. Check which port it's on:
   ```bash
   ls /dev/tty*
   # Look for /dev/ttyACM0 or /dev/ttyUSB0
   ```
3. Run the wired script:
   ```bash
   ./run_wired.sh
   ```

#### Windows:
1. Plug in your Arduino via USB
2. Check which COM port it's on:
   - Open Device Manager -> Ports (COM & LPT)
   - Look for "Arduino" or "USB Serial" (e.g., COM3, COM4)
3. Edit `run_wired.bat` and change the COM port:
   ```batch
   set ARDUINO_PORT=COM3
   ```
4. Double-click `run_wired.bat` or run in Command Prompt:
   ```cmd
   run_wired.bat
   ```

## Configuration Details

### Wireless Configuration

The wireless Arduino needs to:
- Connect to your Wi-Fi network
- Run a TCP server on port 8888 (or custom port)
- Send data in format: `X = 123 | Y = 456 | Z = 789`

**Environment Variables:**
```bash
ARDUINO_MODE=tcp                    # Enable TCP mode
ARDUINO_TCP_HOST=192.168.4.1       # Arduino's IP address
ARDUINO_TCP_PORT=8888              # Arduino's TCP port
```

### Wired Configuration

**Environment Variables (Linux/Mac):**
```bash
ARDUINO_MODE=serial                # Enable serial mode (default)
ARDUINO_PORT=/dev/ttyACM0         # Serial port (auto-detected if not set)
ARDUINO_BAUD=9600                 # Baud rate (default: 9600)
```

**Environment Variables (Windows):**
```cmd
set ARDUINO_MODE=serial           
set ARDUINO_PORT=COM3             # Check Device Manager for your COM port
set ARDUINO_BAUD=9600
```

### Auto-Detection

If you don't set any environment variables, the app will:
- Automatically detect the Arduino serial port
- Use default settings (9600 baud)
- Work with most Arduino boards out of the box

## Supported Data Formats

The app can parse multiple formats:
- `X = 123 | Y = 456 | Z = 789`
- `X: 123, Y: 456, Z: 789`
- Button states: `HIGH` or `LOW`
- Analog values: any number 0-65535

## Troubleshooting

### Permission Denied (Linux)
If you get "Permission denied" on `/dev/ttyACM0`:
```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### Can't Find Arduino Port

**Linux/Mac:**
```bash
ls -l /dev/tty* | grep -E "ACM|USB"
```

**Windows:**
1. Open Device Manager (Win+X, then select Device Manager)
2. Expand "Ports (COM & LPT)"
3. Look for Arduino or USB Serial Device (e.g., COM3, COM4, COM5)

### Wireless Not Connecting
1. Check Arduino is on same network
2. Verify IP address with `ping <arduino_ip>`
3. Make sure TCP server is running on Arduino
4. Check firewall settings

## ESP8266/ESP32 Example Code

Here's a basic Arduino sketch for wireless connection:

```cpp
#include <ESP8266WiFi.h>
#include <Wire.h>
#include <MPU6050.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
WiFiServer server(8888);
MPU6050 mpu;

void setup() {
  Serial.begin(9600);
  Wire.begin();
  mpu.initialize();
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  server.begin();
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);
    
    client.print("X = ");
    client.print(ax);
    client.print(" | Y = ");
    client.print(ay);
    client.print(" | Z = ");
    client.println(az);
    
    delay(50);
  }
}
```

## Testing Without Arduino

The app runs without an Arduino connected; it falls back to the default gravity value.
