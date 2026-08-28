
import threading
import os


MAKEY_MAKEY_IDS = {
    ('1b4f', '2b74'),
    ('1b4f', '2b75'),
    ('1b4f', '2b96'),
    ('1b4f', '2b97'),
    ('1b4f', '2b93'),
    ('1b4f', '2b94'),
    ('1b4f', '2b92'),
    ('1b4f', '2b76'),
}

MAKEY_MAKEY_PRODUCT_KEYWORDS = ('makey', 'makey makey', 'makeymakey', 'joylab')

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

                if (vid, pid) in MAKEY_MAKEY_IDS:
                    found = True
                    info  = prod_name or f'VID:{vid} PID:{pid}'
                    break

                if any(kw in prod_name.lower() for kw in MAKEY_MAKEY_PRODUCT_KEYWORDS):
                    found = True
                    info  = prod_name
                    break

                # catches clones without a known id
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
