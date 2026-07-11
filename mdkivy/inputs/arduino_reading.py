import os
import re
import time
import socket
import serial
from serial.tools import list_ports

class ArduinoReading:
    """Lightweight non-blocking reader for Arduino data over Serial or TCP (wireless).

    Features:
    - Serial mode: auto-detects a likely Arduino port if none is specified.
    - TCP mode: connects to an ESP/Arduino TCP server (e.g., ESP8266/ESP32 Wi‑Fi bridge).
    - Honors env vars: ARDUINO_MODE, ARDUINO_PORT, ARDUINO_BAUD, ARDUINO_TCP_HOST, ARDUINO_TCP_PORT.
    - Parses multiple formats, e.g. "X = 1 | Y = 2 | Z = 3" or "X: 1, Y: 2, Z: 3".
    - Returns None if no new complete line is available (non-blocking in UI loop).
    """

    def __init__(self, port=None, baud_rate=None, tcp_host=None, tcp_port=None, mode=None):
        # Env overrides
        env_mode = (os.getenv("ARDUINO_MODE") or '').lower().strip()
        env_port = os.getenv("ARDUINO_PORT")
        env_baud = os.getenv("ARDUINO_BAUD")
        env_tcp_host = os.getenv("ARDUINO_TCP_HOST")
        env_tcp_port = os.getenv("ARDUINO_TCP_PORT")

        # Determine transport
        self.mode = (mode or env_mode or '').lower() or ('tcp' if (tcp_host or env_tcp_host) else 'serial')

        # State
        self.serial_connection = None
        self.sock = None
        self._rx_buffer = b""
        self._line_buffer = []  # Buffer to collect X, Y, Z lines
        self._temp_x = None
        self._temp_y = None
        self._temp_z = None
        self.last_xyz = None
        self.last_button = None  # 'HIGH'/'LOW'
        self.last_analog = None  # int

        # Regex patterns - added pattern to match Arduino's newline-separated format
        self._patterns = [
            re.compile(r"X\s*=\s*(-?\d+)\s*\|\s*Y\s*=\s*(-?\d+)\s*\|\s*Z\s*=\s*(-?\d+)"),
            re.compile(r"X\s*:\s*(-?\d+)\s*,\s*Y\s*:\s*(-?\d+)\s*,\s*Z\s*:\s*(-?\d+)"),
            # pattern for "X: value\nY: value\nZ: value" format
            re.compile(r"X\s*:\s*(-?\d+).*?Y\s*:\s*(-?\d+).*?Z\s*:\s*(-?\d+)", re.DOTALL)
        ]
        self._btn_pat = re.compile(r"\b(HIGH|LOW)\b", re.IGNORECASE)
        self._analog_pat = re.compile(r"\b(\d{1,5})\b")  # just a number

        if self.mode == 'tcp':
            # TCP mode (wireless)
            self.tcp_host = tcp_host or env_tcp_host or '192.168.4.1'
            self.tcp_port = int(tcp_port or (env_tcp_port or 8888))
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((self.tcp_host, self.tcp_port))
            self.sock.setblocking(False)
            self.port = f"tcp://{self.tcp_host}:{self.tcp_port}"
            self.baud_rate = None
            time.sleep(0.2)
        else:
            # Serial mode (default)
            self.port = port or env_port or self._auto_detect_port()
            if self.port is None:
                raise RuntimeError("No Arduino port found - Makey Makey skipped, no other serial device detected")
            self.baud_rate = int(baud_rate or (env_baud if env_baud else 115200))
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=0)
            time.sleep(2)

    @staticmethod
    def _find_makey_ports():
        """Return a set of /dev/ttyACM* and /dev/ttyUSB* paths that belong to Makey Makey
        (or similar USB HID+serial) devices, detected via sysfs on Linux.

        Detection order:
          1. Product name contains 'makey' / 'joylab'
          2. VID is 1b4f (SparkFun/JoyLabz)
          3. Device exposes a HID interface (bInterfaceClass 03) alongside the CDC serial
             interface - a real Arduino Uno/Mega/Nano never has a HID interface.
        """
        makey_ports = set()
        tty_root = '/sys/class/tty'
        if not os.path.isdir(tty_root):
            return makey_ports
        for tty_name in os.listdir(tty_root):
            if not (tty_name.startswith('ttyACM') or tty_name.startswith('ttyUSB')):
                continue
            device_link = os.path.join(tty_root, tty_name, 'device')
            if not os.path.exists(device_link):
                continue
            try:
                usb_iface = os.path.realpath(device_link)
                usb_dev   = os.path.dirname(usb_iface)

                # 1. Product name check
                prod_path = os.path.join(usb_dev, 'product')
                if os.path.exists(prod_path):
                    with open(prod_path) as f:
                        prod = f.read().strip().lower()
                    if any(kw in prod for kw in ('makey', 'makeymakey', 'joylab')):
                        makey_ports.add(f'/dev/{tty_name}')
                        continue

                # 2. VID check (SparkFun/JoyLabz)
                vid_path = os.path.join(usb_dev, 'idVendor')
                if os.path.exists(vid_path):
                    with open(vid_path) as f:
                        if f.read().strip() == '1b4f':
                            makey_ports.add(f'/dev/{tty_name}')
                            continue

                # 3. HID interface check - Makey Makey is a keyboard AND a serial port;
                #    real Arduinos (Uno, Mega, Nano) only have CDC interfaces, never HID.
                for entry in os.listdir(usb_dev):
                    iface_class = os.path.join(usb_dev, entry, 'bInterfaceClass')
                    if os.path.exists(iface_class):
                        with open(iface_class) as f:
                            if f.read().strip() == '03':   # 03 = HID
                                makey_ports.add(f'/dev/{tty_name}')
                                break
            except Exception:
                pass
        return makey_ports

    @staticmethod
    def _auto_detect_port():
        """Pick a likely Arduino serial port on Linux.
        Looks for known VID/PID or ttyACM*/ttyUSB* names. Returns a string or default '/dev/ttyACM0'.
        Skips Makey Makey devices even when they report as 'Arduino Leonardo' (VID 2341).
        """
        makey_ports = ArduinoReading._find_makey_ports()

        candidates = []
        try:
            for p in list_ports.comports():
                name = p.device or ""
                desc = (p.description or "").lower()
                hwid = (p.hwid or "").lower()
                if name in makey_ports:
                    print(f"[INFO] Skipping Makey Makey port {name} ({p.description})")
                    continue
                if any(k in desc for k in ["arduino", "ch340", "usb serial", "cp210", "ttyacm", "ttyusb"]) or \
                   any(k in name for k in ["ttyacm", "ttyusb"]) or \
                   any(k in hwid for k in ["2341:", "1a86:", "10c4:"]):
                    candidates.append(name)
        except Exception:
            pass

        if candidates:
            return candidates[0]
        # No suitable port found - don't fall back to a Makey Makey port
        return None

    def _parse_xyz_line(self, line: str):
        # Try existing patterns first (single-line formats)
        for pat in self._patterns[:2]:  # Only the first two patterns
            m = pat.search(line)
            if m:
                x, y, z = map(int, m.groups())
                return x, y, z
        
        # Try to parse individual X:, Y:, Z: lines
        x_match = re.search(r"X\s*:\s*(-?\d+)", line)
        y_match = re.search(r"Y\s*:\s*(-?\d+)", line)
        z_match = re.search(r"Z\s*:\s*(-?\d+)", line)
        
        if x_match:
            self._temp_x = int(x_match.group(1))
        if y_match:
            self._temp_y = int(y_match.group(1))
        if z_match:
            self._temp_z = int(z_match.group(1))
        # when we get Z, thats all three values
            if hasattr(self, '_temp_x') and hasattr(self, '_temp_y'):
                return self._temp_x, self._temp_y, self._temp_z
        
        return None

    def _readline_nonblocking(self):
        """Return one line as bytes (without newline) if available; else None."""
        if self.serial_connection:
            try:
                if self.serial_connection.in_waiting:
                    raw = self.serial_connection.readline()
                    return raw.rstrip(b"\r\n") if raw else None
            except Exception:
                return None
            return None
        elif self.sock:
            try:
                chunk = self.sock.recv(4096)
                if chunk:
                    self._rx_buffer += chunk
            except (BlockingIOError, TimeoutError):
                pass
            except Exception:
                return None
            if b"\n" in self._rx_buffer:
                line, _, rest = self._rx_buffer.partition(b"\n")
                self._rx_buffer = rest
                return line.rstrip(b"\r")
            return None
        return None

    def _consume_and_parse(self):
        raw = self._readline_nonblocking()
        if not raw:
            return False
        try:
            line = raw.decode('utf-8', errors='ignore').strip()
        except Exception:
            return False

        # Parse XYZ
        xyz = self._parse_xyz_line(line)
        if xyz:
            self.last_xyz = xyz

        # Parse HIGH/LOW
        m = self._btn_pat.search(line)
        if m:
            self.last_button = m.group(1).upper()

        # try to get a number from the data
        m2 = self._analog_pat.search(line)
        if m2:
            try:
                val = int(m2.group(1))
                if 0 <= val <= 65535:
                    self.last_analog = val
            except Exception:
                pass
        return True

    def get_xyz(self):
        """Return (x, y, z) if available. Always tries to read new data. Non-blocking."""
        try:
            self._consume_and_parse()
            return self.last_xyz
        except Exception:
            return None

    def get_button_state(self):
        """Return 'HIGH'/'LOW' if present; else None."""
        self._consume_and_parse()
        return self.last_button

    def get_analog(self):
        """Return last analog reading if present; else None."""
        self._consume_and_parse()
        return self.last_analog

    @property
    def connection_info(self):
        if self.sock:
            return f"tcp://{getattr(self, 'tcp_host', '?')}:{getattr(self, 'tcp_port', '?')}"
        return f"{self.port} @ {self.baud_rate}"

    def close(self):
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
