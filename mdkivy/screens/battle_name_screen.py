"""Player name entry for battle mode.

Window-level key events avoid TextInput focus problems on Linux.
"""

import os, math, time as _time
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.clock import Clock
from mdkivy.screens.name_filter import is_clean

_ACCENT = (0.31, 0.76, 0.97, 1.0)
_CYAN   = (0.25, 0.80, 1.00, 1.0)
_PURPLE = (0.62, 0.38, 1.00, 1.0)
_MUTED  = (0.55, 0.60, 0.70, 1.0)
_DIM    = (0.42, 0.47, 0.56, 1.0)
_HINT_DEFAULT = 'click a field then type  |  Tab or Enter to switch sides  |  press BATTLE to start'


class BattleNameScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root       = FloatLayout()
        self.add_widget(self._root)

        self._left_text  = ''
        self._right_text = ''
        self._active     = 'left'
        self._cursor_on  = True

        self._cursor_ev  = None
        self._pulse_ev   = None
        self._ready      = False
        self._font_scaled = []

        self._build_ui()
        Window.bind(on_resize=self._rescale)


    def _scale(self, widget, frac):
        """Track font size as a fraction of window height."""
        self._font_scaled.append((widget, frac))
        widget.font_size = max(9.0, Window.height * frac)
        return widget

    def _rescale(self, *_):
        for widget, frac in self._font_scaled:
            widget.font_size = max(9.0, Window.height * frac)

    def _build_ui(self):
        with self._root.canvas.before:
            Color(0.02, 0.025, 0.06, 1)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(pos=self._sync_bg, size=self._sync_bg)

        title = Label(
            text='MOLECULAR BATTLE', bold=True,
            size_hint=(0.8, 0.08),
            pos_hint={'center_x': 0.5, 'top': 0.96},
            color=_ACCENT,
            halign='center', valign='middle',
        )
        self._scale(title, 0.042)
        title.bind(size=title.setter('text_size'))
        self._root.add_widget(title)

        self._hint = Label(
            text=_HINT_DEFAULT,
            size_hint=(0.8, 0.05),
            pos_hint={'center_x': 0.5, 'top': 0.875},
            color=_DIM,
            halign='center', valign='middle',
        )
        self._scale(self._hint, 0.018)
        self._hint.bind(size=self._hint.setter('text_size'))
        self._root.add_widget(self._hint)

        vs = Label(
            text='VS', bold=True,
            size_hint=(0.12, 0.10),
            pos_hint={'center_x': 0.5, 'center_y': 0.615},
            color=(*_DIM[:3], 0.85),
            halign='center', valign='middle',
        )
        self._scale(vs, 0.036)
        vs.bind(size=vs.setter('text_size'))
        self._root.add_widget(vs)

        for text, cx, col in (('PLAYER 1', 0.25, _CYAN),
                              ('PLAYER 2', 0.75, _PURPLE)):
            lbl = Label(text=text, bold=True,
                        size_hint=(0.33, 0.05),
                        pos_hint={'center_x': cx, 'top': 0.745},
                        color=col, halign='center', valign='middle')
            self._scale(lbl, 0.020)
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

        self._left_box,  self._left_display,  \
            self._left_bd_color,  self._left_bd_line  = self._build_box(0.25, _CYAN)
        self._right_box, self._right_display, \
            self._right_bd_color, self._right_bd_line = self._build_box(0.75, _PURPLE)

        self._battle_btn = Button(
            text='BATTLE', bold=True,
            size_hint=(0.24, 0.085),
            pos_hint={'center_x': 0.5, 'center_y': 0.33},
            background_normal='', background_down='',
            background_color=(0, 0, 0, 0),
            color=_ACCENT,
        )
        self._scale(self._battle_btn, 0.028)
        with self._battle_btn.canvas.before:
            Color(0.04, 0.07, 0.16, 0.92)
            self._btn_bg = RoundedRectangle(
                pos=self._battle_btn.pos, size=self._battle_btn.size, radius=[12])
            Color(*_ACCENT[:3], 0.65)
            self._btn_bd = Line(
                rounded_rectangle=(*self._battle_btn.pos,
                                   *self._battle_btn.size, 12),
                width=1.5)
        self._battle_btn.bind(
            pos=self._sync_btn, size=self._sync_btn,
            on_release=self._start_battle,
        )
        self._root.add_widget(self._battle_btn)

        back = Button(
            text='BACK', bold=True,
            size_hint=(0.055, 0.036),
            pos_hint={'x': 0.008, 'y': 0.958},
            background_normal='', background_down='',
            background_color=(0, 0, 0, 0),
            color=_MUTED,
        )
        self._scale(back, 0.016)
        with back.canvas.before:
            Color(0.04, 0.06, 0.14, 0.90)
            _bbg = RoundedRectangle(pos=back.pos, size=back.size, radius=[6])
            Color(*_MUTED[:3], 0.50)
            _bbd = Line(rounded_rectangle=(*back.pos, *back.size, 6), width=1.2)
        def _bsync(*_):
            _bbg.pos = back.pos
            _bbg.size = back.size
            _bbd.rounded_rectangle = (*back.pos, *back.size, 6)
        back.bind(pos=_bsync, size=_bsync, on_press=self._go_back)
        self._root.add_widget(back)

        self._update_displays()

    def _build_box(self, center_x, border_col):
        """Clickable name field - returns (box, display, border colour, border line)."""
        box = FloatLayout(
            size_hint=(0.34, 0.115),
            pos_hint={'center_x': center_x, 'center_y': 0.615},
        )
        with box.canvas.before:
            Color(0.035, 0.05, 0.11, 0.92)
            fill = RoundedRectangle(pos=box.pos, size=box.size, radius=[10])
            bd_col = Color(*border_col[:3], 1.0)
            bd_line = Line(rounded_rectangle=(*box.pos, *box.size, 10), width=1.5)

        def _sync(*_):
            fill.pos = box.pos
            fill.size = box.size
            bd_line.rounded_rectangle = (*box.pos, *box.size, 10)
        box.bind(pos=_sync, size=_sync)

        display = Label(
            text='', bold=True,
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0},
            halign='center', valign='middle',
            color=(1, 1, 1, 1),
        )
        self._scale(display, 0.034)
        display.bind(size=display.setter('text_size'))
        box.add_widget(display)
        self._root.add_widget(box)
        return box, display, bd_col, bd_line

    def on_touch_down(self, touch):
        if getattr(touch, 'multitouch_sim', False):
            return True
        if touch.grab_current is not None:
            return super().on_touch_down(touch)

        # raw touch is wrong on the exhibit screen
        if getattr(touch, 'device', '') == 'mouse' \
                and getattr(touch, 'button', 'left') == 'left':
            if self._left_box.collide_point(*touch.pos):
                self._active = 'left'
                self._update_displays()
            elif self._right_box.collide_point(*touch.pos):
                self._active = 'right'
                self._update_displays()

        return super().on_touch_down(touch)

    def _on_key(self, window, key, scancode, codepoint, modifiers):
        if not self._ready:
            return

        if key == 9:
            self._active = 'right' if self._active == 'left' else 'left'

        elif key == 13:
            self._active = 'right' if self._active == 'left' else 'left'

        elif key == 8:
            if self._active == 'left':
                self._left_text = self._left_text[:-1]
            else:
                self._right_text = self._right_text[:-1]

        elif key == 27:
            if self._active == 'left':
                self._left_text = ''
            else:
                self._right_text = ''

        elif codepoint and len(codepoint) == 1 and codepoint.isprintable():
            if self._active == 'left' and len(self._left_text) < 18:
                self._left_text += codepoint
            elif self._active == 'right' and len(self._right_text) < 18:
                self._right_text += codepoint

        self._update_displays()

    def _update_displays(self):
        cur = '|' if self._cursor_on else ' '

        if self._active == 'left':
            self._left_display.color   = (1.0, 1.0, 1.0, 1.0)
            self._right_display.color  = (*_DIM[:3], 1.0)
            self._left_display.text    = (self._left_text or '') + cur
            self._right_display.text   = self._right_text if self._right_text else 'enter name...'
            self._left_bd_color.rgba   = (*_CYAN[:3],   0.95)
            self._right_bd_color.rgba  = (*_PURPLE[:3], 0.30)
            self._left_bd_line.width   = 2.0
            self._right_bd_line.width  = 1.0
        else:
            self._left_display.color   = (*_DIM[:3], 1.0)
            self._right_display.color  = (1.0, 1.0, 1.0, 1.0)
            self._left_display.text    = self._left_text if self._left_text else 'enter name...'
            self._right_display.text   = (self._right_text or '') + cur
            self._left_bd_color.rgba   = (*_CYAN[:3],   0.30)
            self._right_bd_color.rgba  = (*_PURPLE[:3], 0.95)
            self._left_bd_line.width   = 1.0
            self._right_bd_line.width  = 2.0

    def _cursor_blink(self, dt):
        self._cursor_on = not self._cursor_on
        self._update_displays()

    def _sync_bg(self, *_):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size

    def _sync_btn(self, *_):
        self._btn_bg.pos  = self._battle_btn.pos
        self._btn_bg.size = self._battle_btn.size
        self._btn_bd.rounded_rectangle = (
            *self._battle_btn.pos, *self._battle_btn.size, 14)


    def on_enter(self, *args):
        self._ready      = False
        self._left_text  = ''
        self._right_text = ''
        self._active     = 'left'
        self._cursor_on  = True
        self._update_displays()
        Window.unbind(on_key_down=self._on_key)
        Window.bind(on_key_down=self._on_key)
        self._cursor_ev = Clock.schedule_interval(self._cursor_blink, 0.5)
        self._pulse_ev  = Clock.schedule_interval(self._pulse_tick,   1 / 30)
        Clock.schedule_once(lambda *_: setattr(self, '_ready', True), 0.8)

    def on_pre_leave(self, *args):
        self._ready = False
        Window.unbind(on_key_down=self._on_key)
        for ev in (self._cursor_ev, self._pulse_ev):
            if ev:
                ev.cancel()
        self._cursor_ev = self._pulse_ev = None

    def _pulse_tick(self, dt):
        t = _time.time()
        self._btn_bd.width = 1.5 + 0.5 * math.sin(t * 2.4)

    def _start_battle(self, *_):
        if not self._ready:
            return
        left_name  = self._left_text.strip()  or 'Player 1'
        right_name = self._right_text.strip() or 'Player 2'

        bad_left  = not is_clean(left_name)
        bad_right = not is_clean(right_name)
        if bad_left or bad_right:
            if bad_left:
                self._left_text = ''
            if bad_right:
                self._right_text = ''
            self._update_displays()
            self._hint.text  = 'that name is not allowed here - please choose a different one'
            self._hint.color = (0.95, 0.40, 0.45, 1.0)
            return
        self._hint.text  = _HINT_DEFAULT
        self._hint.color = _DIM

        if self.manager:
            bs = self.manager.get_screen('BattleScreen')
            bs._left_name  = left_name
            bs._right_name = right_name
            self.manager.current = 'BattleScreen'

    def _go_back(self, *_):
        if self.manager:
            self.manager.current = 'LandingScreen'
