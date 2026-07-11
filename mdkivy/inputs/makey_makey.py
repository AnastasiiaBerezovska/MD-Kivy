# Makey Makey detection - runs in the background and checks if one is plugged in
# Makey Makey shows up as a USB keyboard so we look for its vendor/product ID
# when connected the app shows the key legend and arrow keys start controlling the simulation

import threading
import os


# these are the USB vendor/product IDs for different versions of the Makey Makey / JoyLabz boards
# VID 1b4f = SparkFun Electronics (parent of JoyLabz / Makey Makey)
MAKEY_MAKEY_IDS = {
    ('1b4f', '2b74'),   # Classic v1.2
    ('1b4f', '2b75'),   # Classic v1.2 alternate
    ('1b4f', '2b96'),   # Go version
    ('1b4f', '2b97'),   # Go version alternate
    ('1b4f', '2b93'),   # Makey Max / newer variants
    ('1b4f', '2b94'),
    ('1b4f', '2b92'),
    ('1b4f', '2b76'),
}

# Fallback: if VID/PID is not in the list, match by product name containing these strings
MAKEY_MAKEY_PRODUCT_KEYWORDS = ('makey', 'makey makey', 'makeymakey', 'joylab')

# what each key does when Makey Makey is connected
# shown in the legend panel when its plugged in
# Covers: base board arrows, Player 2 D-pad (W/A/S/D/F/G), Makey Max keyboard section
KEY_LEGEND = [
    ('Space', 'Spawn  LEFT  side  (Left Makey)'),
    ('Enter', 'Spawn  RIGHT  side  (Right Makey)'),
    ('W / A', 'Gravity +'),
    ('S',     'Gravity -'),
    ('D',     'Epsilon -'),
    ('F',     'Sigma -'),
    ('G',     'Delta -'),
    ('↑',     'Gravity +'),
    ('↓',     'Gravity -'),
    ('→',     'Epsilon +'),
    ('←',     'Epsilon -'),
]


class MakeyMakeyMonitor:
    # polls the USB device list every 2 seconds in a background thread
    # just read .connected and .device_info from the main thread, they update automatically

    def __init__(self, poll_interval: float = 2.0):
        self.connected   = False
        self.device_info = ''
        self._interval   = poll_interval
        self._stop       = threading.Event()
        self._thread     = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.wait(self._interval):
            self._check()

    def _check(self):
        # Scan /sys/bus/usb/devices for any Makey Makey variant.
        # Detection order:
        #   1. VID/PID in known list
        #   2. Product name contains 'makey' / 'joylab'
        #   3. Device has BOTH a HID interface (class 03) and a CDC serial interface (class 02)
        #      - Makey Makey is a USB keyboard that also creates a ttyACM port.
        #      Real Arduinos (Uno, Mega, Nano) have no HID interface.
        usb_root = '/sys/bus/usb/devices'
        if not os.path.isdir(usb_root):
            return
        found = False
        info  = ''
        try:
            for dev in os.listdir(usb_root):
                dev_path = os.path.join(usb_root, dev)
                vid_path = os.path.join(dev_path, 'idVendor')
                pid_path = os.path.join(dev_path, 'idProduct')
                if not (os.path.exists(vid_path) and os.path.exists(pid_path)):
                    continue
                with open(vid_path) as f:
                    vid = f.read().strip()
                with open(pid_path) as f:
                    pid = f.read().strip()

                prod_name = ''
                prod_path = os.path.join(dev_path, 'product')
                if os.path.exists(prod_path):
                    with open(prod_path) as f:
                        prod_name = f.read().strip()

                # 1. Known VID/PID
                if (vid, pid) in MAKEY_MAKEY_IDS:
                    found = True
                    info  = prod_name or f'VID:{vid} PID:{pid}'
                    break

                # 2. Product name keyword
                if any(kw in prod_name.lower() for kw in MAKEY_MAKEY_PRODUCT_KEYWORDS):
                    found = True
                    info  = prod_name
                    break

                # 3. HID + CDC interface combination (catches boards that report as
                #    'Arduino Leonardo' but are actually Makey Makey)
                has_hid = False
                has_cdc = False
                try:
                    for entry in os.listdir(dev_path):
                        iface_class_path = os.path.join(dev_path, entry, 'bInterfaceClass')
                        if os.path.exists(iface_class_path):
                            with open(iface_class_path) as f:
                                cls = f.read().strip()
                            if cls == '03':
                                has_hid = True
                            elif cls == '02':
                                has_cdc = True
                except Exception:
                    pass
                if has_hid and has_cdc:
                    found = True
                    info  = prod_name or f'VID:{vid} PID:{pid}'
                    break
        except Exception:
            pass
        self.connected   = found
        self.device_info = info

    def stop(self):
        self._stop.set()
