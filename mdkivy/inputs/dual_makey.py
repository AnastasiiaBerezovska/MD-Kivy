"""
DualMakeyInput - reads events from two Makey Makey devices independently
using evdev, so both can send the same key (Space/Space) and still be told apart.

Requires: pip install evdev
Requires: user must be in the 'input' group
          sudo usermod -aG input $USER  (then log out and back in)
"""

import threading
import glob
import time as _time
from kivy.clock import Clock

MAKEY_KEYWORDS = ('makey', 'arduino leonardo', 'joylab', 'makeymakey')


def _find_makeys():
    """Return only the Keyboard interfaces from each connected Makey Makey.

    Each physical Makey Makey exposes multiple event devices (Keyboard, Mouse,
    generic HID).  We only want the Keyboard interface from each one so we
    don't accidentally double-trigger or pick the wrong device.

    Filter: name matches a Makey keyword AND 'keyboard' is in the name.

    Example - two Makeys produce 5 devices total:
      event15: JoyLabz Makey Makey v1.30aa  Keyboard  <- KEEP (LEFT)
      event16: JoyLabz Makey Makey v1.30aa  Mouse     <- skip
      event17: JoyLabz Makey Makey v1.30aa            <- skip
      event18: Arduino LLC Arduino Leonardo Mouse      <- skip
      event19: Arduino LLC Arduino Leonardo Keyboard   <- KEEP (RIGHT)
    """
    try:
        import evdev
    except ImportError:
        print('[DUAL MAKEY] evdev not installed - run: pip install evdev')
        return []

    found = []
    for path in sorted(glob.glob('/dev/input/event*')):
        try:
            dev = evdev.InputDevice(path)
            name_lower  = dev.name.lower()
            is_makey    = any(kw in name_lower for kw in MAKEY_KEYWORDS)
            is_keyboard = 'keyboard' in name_lower
            if is_makey and is_keyboard:
                found.append(dev)
                print(f'[DUAL MAKEY] Found keyboard: {dev.path}  ({dev.name})')
            else:
                dev.close()
        except Exception:
            pass
    return found


class DualMakeyInput:
    """
    Starts background threads watching each Makey Makey keyboard device.
    Any key-down event on device 0 calls left_cb; device 1 calls right_cb.
    Callbacks are dispatched on the Kivy main thread via Clock.schedule_once.

    Events fired in the first second after startup are ignored - evdev replays
    the current key state when a device is first opened, which would otherwise
    spawn a spurious molecule before the simulation is ready.
    """

    def __init__(self, left_cb, right_cb):
        self._left_cb    = left_cb
        self._right_cb   = right_cb
        self._stop       = threading.Event()
        self._threads    = []
        self._devices    = []
        # ignore events for 1 second after startup to avoid spurious state replay
        self._ready_after = _time.monotonic() + 1.0
        self._start()

    def _start(self):
        devices = _find_makeys()
        self._devices = devices
        cbs = [self._left_cb, self._right_cb]

        if not devices:
            print('[DUAL MAKEY] No Makey Makey devices found or you have no permission.')
            print('             Run:  sudo usermod -aG input $USER  then re-login.')
            return

        for i, dev in enumerate(devices[:2]):
            cb   = cbs[i]
            side = 'LEFT' if i == 0 else 'RIGHT'
            print(f'[DUAL MAKEY] {side} -> {dev.path}  ({dev.name})')
            t = threading.Thread(
                target=self._read_loop,
                args=(dev, cb, side),
                daemon=True, # threads will close automatically when the main program exits
                name=f'DualMakey-{side}',
            )
            t.start()
            self._threads.append(t)

        if len(devices) == 1:
            print('[DUAL MAKEY] Only 1 MakeyMakey input So the right side would not respond.')
        elif len(devices) >= 2:
            print(f'[DUAL MAKEY] Ready is LEFT={devices[0].name}, RIGHT={devices[1].name}')

    def _read_loop(self, device, callback, side):
        # minimum seconds between accepted presses for this device
        # filters contact bounce (rapid hardware key events from a single press)
        DEBOUNCE = 0.35
        last_fire = 0.0
        try:
            import evdev
            for event in device.read_loop():
                if self._stop.is_set():
                    break
                # skip all events during the startup grace period
                if _time.monotonic() < self._ready_after:
                    continue
                if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                    now = _time.monotonic()
                    if now - last_fire < DEBOUNCE:
                        continue   # bounce isto ignore
                    last_fire = now
                    Clock.schedule_once(lambda dt, cb=callback: cb())
        except Exception as e:
            print(f'[DUAL MAKEY] {side} device error: {e}')

    def stop(self):
        self._stop.set()
        for dev in self._devices:
            try:
                dev.close()
            except Exception:
                pass
