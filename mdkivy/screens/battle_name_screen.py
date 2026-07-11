"""
BattleNameScreen - name-entry lobby.

TextInput is NOT used because Kivy's TextInput has keyboard-focus issues on
some Linux setups. Instead this screen binds Window.on_key_down directly and
displays typed text in Labels. Click a box (or press Tab / Enter) to switch
the active field.
"""

import os, math, time as _time
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.clock import Clock
from mdkivy.paths import FONT_IMPACT
from mdkivy.screens.name_filter import is_clean

_FONT   = FONT_IMPACT
_CYAN   = (0.25, 0.80, 1.0, 1.0)
_PURPLE = (0.62, 0.38, 1.0, 1.0)
_HINT_DEFAULT = 'click a field then type  |  Tab or Enter to switch sides  |  press BATTLE! to start'


class BattleNameScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root       = FloatLayout()
        self.add_widget(self._root)

        # text state
        self._left_text  = ''
        self._right_text = ''
        self._active     = 'left'   # 'left' | 'right'
        self._cursor_on  = True

        # event handles
        self._cursor_ev  = None
        self._pulse_ev   = None
        self._ready      = False

        self._build_ui()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self):
        # background
        with self._root.canvas.before:
            Color(0.01, 0.02, 0.06, 1)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(pos=self._sync_bg, size=self._sync_bg)

        # title
        title = Label(
            text='MOLECULAR BATTLE',
            font_name=_FONT, font_size=48,
            size_hint=(0.7, 0.12),
            pos_hint={'center_x': 0.5, 'top': 0.97},
            color=(1.0, 0.88, 0.20, 1),
            halign='center', valign='middle',
            outline_color=(0.6, 0.4, 0, 1), outline_width=3,
        )
        title.bind(size=title.setter('text_size'))
        self._root.add_widget(title)

        self._hint = Label(
            text=_HINT_DEFAULT,
            font_name=_FONT, font_size=15,
            size_hint=(0.75, 0.06),
            pos_hint={'center_x': 0.5, 'top': 0.84},
            color=(0.50, 0.50, 0.65, 0.85),
            halign='center', valign='middle',
        )
        self._hint.bind(size=self._hint.setter('text_size'))
        self._root.add_widget(self._hint)

        # VS
        vs = Label(
            text='VS',
            font_name=_FONT, font_size=64,
            size_hint=(0.12, 0.14),
            pos_hint={'center_x': 0.5, 'center_y': 0.62},
            color=(1.0, 0.90, 0.25, 0.95),
            halign='center', valign='middle',
            outline_color=(0.5, 0.4, 0, 1), outline_width=2,
        )
        vs.bind(size=vs.setter('text_size'))
        self._root.add_widget(vs)

        # player headers
        for text, cx, col in [('PLAYER  1', 0.22, _CYAN),
                               ('PLAYER  2', 0.78, _PURPLE)]:
            lbl = Label(text=text, font_name=_FONT, font_size=22,
                        size_hint=(0.33, 0.07),
                        pos_hint={'center_x': cx, 'top': 0.78},
                        color=col, halign='center', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

        # text-field boxes
        self._left_box,  self._left_display,  \
            self._left_bd_color,  self._left_bd_line  = self._build_box(
                0.22, _CYAN,   (0.02, 0.06, 0.16, 1))
        self._right_box, self._right_display, \
            self._right_bd_color, self._right_bd_line = self._build_box(
                0.78, _PURPLE, (0.10, 0.05, 0.16, 1))

        # BATTLE! button
        self._battle_btn = Button(
            text='>>  BATTLE!  <<',
            font_name=_FONT, font_size=34,
            size_hint=(0.30, 0.10),
            pos_hint={'center_x': 0.5, 'center_y': 0.34},
            background_normal='', background_color=(0, 0, 0, 0),
            color=(1.0, 0.92, 0.30, 1),
        )
        with self._battle_btn.canvas.before:
            Color(0.10, 0.08, 0.01, 1)
            self._btn_bg = RoundedRectangle(
                pos=self._battle_btn.pos, size=self._battle_btn.size, radius=[14])
            Color(1.0, 0.80, 0.15, 0.90)
            self._btn_bd = Line(
                rounded_rectangle=(*self._battle_btn.pos, *self._battle_btn.size, 14),
                width=2.4)
        self._battle_btn.bind(
            pos=self._sync_btn, size=self._sync_btn,
            on_release=self._start_battle,
        )
        self._root.add_widget(self._battle_btn)

        # BACK button
        back = Button(
            text='BACK', font_name=_FONT, font_size=16,
            size_hint=(0.07, 0.045),
            pos_hint={'x': 0.01, 'y': 0.955},
            background_normal='', background_color=(0, 0, 0, 0),
            color=(0.55, 0.75, 1.0, 1),
        )
        with back.canvas.before:
            Color(0.04, 0.10, 0.22, 0.92)
            _bbg = RoundedRectangle(pos=back.pos, size=back.size, radius=[6])
            Color(0.30, 0.60, 1.0, 0.65)
            _bbd = Line(rounded_rectangle=(*back.pos, *back.size, 6), width=1.2)
        def _bsync(*_):
            _bbg.pos = back.pos; _bbg.size = back.size
            _bbd.rounded_rectangle = (*back.pos, *back.size, 6)
        back.bind(pos=_bsync, size=_bsync, on_press=self._go_back)
        self._root.add_widget(back)

        self._update_displays()

    def _build_box(self, center_x, border_col, bg_col):
        """Styled clickable text-field box - returns (box, display_label, bd_color, bd_line)."""
        box = FloatLayout(
            size_hint=(0.35, 0.15),
            pos_hint={'center_x': center_x, 'center_y': 0.62},
        )
        with box.canvas.before:
            Color(*bg_col)
            fill = RoundedRectangle(pos=box.pos, size=box.size, radius=[8])
            bd_col = Color(*border_col)
            bd_line = Line(rounded_rectangle=(*box.pos, *box.size, 8), width=2.0)

        def _sync(*_):
            fill.pos  = box.pos;  fill.size = box.size
            bd_line.rounded_rectangle = (*box.pos, *box.size, 8)
        box.bind(pos=_sync, size=_sync)

        display = Label(
            text='',
            font_size=38,
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0},  # without this FloatLayout leaves Label at screen (0,0)
            halign='left', valign='middle',
            color=(1, 1, 1, 1),
            padding=[14, 0],
        )
        display.bind(size=display.setter('text_size'))
        box.add_widget(display)
        self._root.add_widget(box)
        return box, display, bd_col, bd_line

    # ==================================================================
    # Touch - click a box to make it active
    # ==================================================================

    def on_touch_down(self, touch):
        if getattr(touch, 'multitouch_sim', False):
            return True
        if touch.grab_current is not None:
            return super().on_touch_down(touch)

        # Only treat a touch as a box-select if it comes from the real touchscreen.
        # Phantom mouse events (device='mouse') land at the cursor position, not the
        # finger position, so skip box logic - but still let super() run so buttons work.
        if getattr(touch, 'device', '') != 'mouse':
            if hasattr(self, '_left_box') and self._left_box.collide_point(*touch.pos):
                self._active = 'left'
                self._update_displays()
            elif hasattr(self, '_right_box') and self._right_box.collide_point(*touch.pos):
                self._active = 'right'
                self._update_displays()

        return super().on_touch_down(touch)

    # ==================================================================
    # Keyboard capture (Window-level, no TextInput focus needed)
    # ==================================================================

    def _on_key(self, window, key, scancode, codepoint, modifiers):
        if not self._ready:
            return

        if key == 9:            # Tab - flip field
            self._active = 'right' if self._active == 'left' else 'left'

        elif key == 13:         # Enter - only moves focus, never starts battle
            self._active = 'right' if self._active == 'left' else 'left'

        elif key == 8:          # Backspace
            if self._active == 'left':
                self._left_text = self._left_text[:-1]
            else:
                self._right_text = self._right_text[:-1]

        elif key == 27:         # Escape - clear field
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

    # ==================================================================
    # Display update
    # ==================================================================

    def _update_displays(self):
        cur = '|' if self._cursor_on else ' '

        if self._active == 'left':
            self._left_display.color   = (1.0, 1.0, 1.0, 1.0)
            self._right_display.color  = (0.45, 0.45, 0.50, 1.0)
            self._left_display.text    = (self._left_text or '') + cur
            self._right_display.text   = self._right_text if self._right_text else 'enter name...'
            self._left_bd_color.rgba   = (*_CYAN[:3],   1.00)
            self._right_bd_color.rgba  = (*_PURPLE[:3], 0.38)
            self._left_bd_line.width   = 2.4
            self._right_bd_line.width  = 1.2
        else:
            self._left_display.color   = (0.45, 0.45, 0.50, 1.0)
            self._right_display.color  = (1.0, 1.0, 1.0, 1.0)
            self._left_display.text    = self._left_text if self._left_text else 'enter name...'
            self._right_display.text   = (self._right_text or '') + cur
            self._left_bd_color.rgba   = (*_CYAN[:3],   0.38)
            self._right_bd_color.rgba  = (*_PURPLE[:3], 1.00)
            self._left_bd_line.width   = 1.2
            self._right_bd_line.width  = 2.4

    def _cursor_blink(self, dt):
        self._cursor_on = not self._cursor_on
        self._update_displays()

    # ==================================================================
    # Sync helpers
    # ==================================================================

    def _sync_bg(self, *_):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size

    def _sync_btn(self, *_):
        self._btn_bg.pos  = self._battle_btn.pos
        self._btn_bg.size = self._battle_btn.size
        self._btn_bd.rounded_rectangle = (
            *self._battle_btn.pos, *self._battle_btn.size, 14)

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def on_enter(self, *args):
        self._ready      = False
        self._left_text  = ''
        self._right_text = ''
        self._active     = 'left'
        self._cursor_on  = True
        self._update_displays()
        Window.unbind(on_key_down=self._on_key)   # prevent double-binding
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
        self._btn_bd.width = 2.0 + 0.8 * math.sin(t * 2.4)

    # ==================================================================
    # Actions
    # ==================================================================

    def _start_battle(self, *_):
        if not self._ready:
            return
        left_name  = self._left_text.strip()  or 'Player 1'
        right_name = self._right_text.strip() or 'Player 2'

        # Screen names before they reach the arena and the leaderboard
        bad_left  = not is_clean(left_name)
        bad_right = not is_clean(right_name)
        if bad_left or bad_right:
            if bad_left:
                self._left_text = ''
            if bad_right:
                self._right_text = ''
            self._update_displays()
            self._hint.text  = 'that name is not allowed here - please choose a different one'
            self._hint.color = (1.0, 0.45, 0.35, 1.0)
            return
        self._hint.text  = _HINT_DEFAULT
        self._hint.color = (0.50, 0.50, 0.65, 0.85)

        if self.manager:
            bs = self.manager.get_screen('BattleScreen')
            bs._left_name  = left_name
            bs._right_name = right_name
            self.manager.current = 'BattleScreen'

    def _go_back(self, *_):
        if self.manager:
            self.manager.current = 'LandingScreen'
