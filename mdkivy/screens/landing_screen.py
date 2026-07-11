import math
import os

from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
from mdkivy.paths import FONT_IMPACT


_FONT = FONT_IMPACT


def _make_nav_btn(text, accent, on_press_cb, pos_hint, size_hint=(0.20, 0.09)):
    """Glowing nav button with a coloured border and dark fill."""
    r, g, b = accent
    btn = Button(
        text=text,
        font_name=_FONT,
        font_size=34,
        color=(1, 1, 1, 1),
        background_normal='',
        background_color=(0, 0, 0, 0),
        size_hint=size_hint,
        pos_hint=pos_hint,
    )
    with btn.canvas.before:
        Color(r * 0.08, g * 0.08, b * 0.08, 0.92)
        _bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[10])
        Color(r, g, b, 0.80)
        _border = Line(rounded_rectangle=(btn.x, btn.y, btn.width, btn.height, 10), width=1.6)

    def _sync(*_):
        _bg.pos = btn.pos
        _bg.size = btn.size
        _border.rounded_rectangle = (btn.x, btn.y, btn.width, btn.height, 10)

    btn.bind(pos=_sync, size=_sync, on_press=lambda *_: on_press_cb())
    return btn


class LandingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._root = FloatLayout()

        # Pure black background
        with self._root.canvas.before:
            Color(0, 0, 0, 1)
            self._bg = RoundedRectangle(pos=self._root.pos, size=self._root.size, radius=[0])
        self._root.bind(pos=self._update_bg, size=self._update_bg)

        # Title labels - shifted up slightly to leave room for the button row
        self._label1 = Label(
            text="MOLECULAR DYNAMICS",
            font_name=_FONT,
            color=(0.3, 0.92, 1.0, 1),
            outline_color=(0, 0.7, 1, 1),
            outline_width=3,
            bold=True,
            pos_hint={"center_x": 0.5, "center_y": 0.60},
            size_hint=(1, None),
            height=80,
        )

        self._label2 = Label(
            text="SIMULATION",
            font_name=_FONT,
            color=(0.88, 0.82, 1.0, 1),
            outline_color=(0.5, 0.2, 1.0, 1),
            outline_width=3,
            bold=True,
            pos_hint={"center_x": 0.5, "center_y": 0.48},
            size_hint=(1, None),
            height=65,
        )

        self._root.bind(size=self._update_font_sizes)
        self._root.add_widget(self._label1)
        self._root.add_widget(self._label2)

        # -- Bottom navigation buttons --------------------------------------
        # START (lower-center-left)
        self._btn_start = _make_nav_btn(
            text="START",
            accent=(0.3, 0.92, 1.0),
            on_press_cb=self._go_to_game,
            pos_hint={"center_x": 0.38, "y": 0.06},
        )

        # GAME (lower-center-right)
        self._btn_game = _make_nav_btn(
            text="GAME",
            accent=(0.75, 0.45, 1.0),
            on_press_cb=self._go_to_start,
            pos_hint={"center_x": 0.62, "y": 0.06},
        )

        self._root.add_widget(self._btn_start)
        self._root.add_widget(self._btn_game)

        self.add_widget(self._root)

        # pulse animation via Clock
        self._pulse_t = 0.0
        self._pulse_event = None

    # -- background sync ----------------------------------------------------
    def _update_bg(self, instance, *_):
        self._bg.pos = instance.pos
        self._bg.size = instance.size

    def _update_font_sizes(self, instance, size):
        w = size[0]
        self._label1.font_size = max(24, w * 0.07)
        self._label2.font_size = max(18, w * 0.055)

    # -- navigation ---------------------------------------------------------
    def _go_to_game(self):
        if self.manager:
            self.manager.current = "GameScreen"

    def _go_to_start(self):
        if self.manager:
            self.manager.current = "BattleNameScreen"

    # -- pulse animation ----------------------------------------------------
    def _pulse_tick(self, dt):
        self._pulse_t += dt
        t = self._pulse_t

        ow1 = 3.5 + 1.5 * math.sin(t * 1.8)
        ow2 = 3.0 + 1.2 * math.sin(t * 1.4 + 1.0)
        bright1 = 1.0 + 0.10 * math.sin(t * 2.1)
        bright2 = 1.0 + 0.08 * math.sin(t * 1.7 + 0.5)

        self._label1.outline_width = ow1
        self._label1.color = (
            min(1.0, 0.3 * bright1),
            min(1.0, 0.92 * bright1),
            min(1.0, 1.0 * bright1),
            1,
        )
        self._label2.outline_width = ow2
        self._label2.color = (
            min(1.0, 0.88 * bright2),
            min(1.0, 0.82 * bright2),
            min(1.0, 1.0 * bright2),
            1,
        )

    def on_enter(self, *args):
        self._update_font_sizes(self._root, self._root.size)
        if self._pulse_event is None:
            self._pulse_event = Clock.schedule_interval(self._pulse_tick, 1 / 30)

    def on_leave(self, *args):
        if self._pulse_event is not None:
            self._pulse_event.cancel()
            self._pulse_event = None
