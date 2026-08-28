"""Post-match leaderboard."""

import os, json
from datetime import datetime
from collections import Counter

from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from mdkivy.paths import LEADERBOARD_FILE as _LB_FILE

C_ACCENT = (0.31, 0.76, 0.97)
C_CYAN   = (0.25, 0.80, 1.00)
C_PURPLE = (0.62, 0.38, 1.00)
C_GOLD   = (1.00, 0.78, 0.25)
C_SILVER = (0.78, 0.82, 0.88)
C_BRONZE = (0.85, 0.55, 0.32)
C_MUTED  = (0.58, 0.63, 0.72)
C_DIM    = (0.42, 0.47, 0.56)

COL_W = (0.20, 0.50, 0.30)


def _load():
    try:
        with open(_LB_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save(entries):
    try:
        with open(_LB_FILE, 'w') as f:
            # keep the save file small
            json.dump(entries[-100:], f, indent=2)
    except Exception:
        pass


class LeaderboardScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.winner_name = ''
        self.winner_side = 'left'
        self._font_scaled = []
        self._row_scaled  = []
        self._root = FloatLayout()
        self.add_widget(self._root)
        self._build_ui()
        Window.bind(on_resize=self._rescale)


    def _scale(self, widget, font_frac, height_frac=None, row=False):
        """Track font size (and optionally row height) against window height."""
        target = self._row_scaled if row else self._font_scaled
        target.append((widget, font_frac, height_frac))
        self._apply_scale(widget, font_frac, height_frac)
        return widget

    @staticmethod
    def _apply_scale(widget, font_frac, height_frac):
        widget.font_size = max(9.0, Window.height * font_frac)
        if height_frac is not None:
            widget.height = max(16.0, Window.height * height_frac)

    def _rescale(self, *_):
        for widget, font_frac, height_frac in self._font_scaled + self._row_scaled:
            self._apply_scale(widget, font_frac, height_frac)


    def _build_ui(self):
        with self._root.canvas.before:
            Color(0.02, 0.025, 0.06, 1)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(pos=self._sync_bg, size=self._sync_bg)

        title = Label(
            text='LEADERBOARD', bold=True,
            size_hint=(0.8, 0.08),
            pos_hint={'center_x': 0.5, 'top': 0.99},
            color=(*C_ACCENT, 1),
            halign='center', valign='middle',
        )
        self._scale(title, 0.042)
        title.bind(size=title.setter('text_size'))
        self._root.add_widget(title)

        self._build_winner_card()
        self._build_table()
        self._build_buttons()

    def _build_winner_card(self):
        """Card is placed by the layout; _pull_animation only slides the
        wrapper, so the card cannot land off-centre."""
        self._card_wrap = FloatLayout(size_hint=(None, None))
        self._root.bind(size=lambda *_: setattr(
            self._card_wrap, 'size', self._root.size))

        self._winner_card = FloatLayout(
            size_hint=(0.40, 0.19),
            pos_hint={'center_x': 0.5, 'center_y': 0.755})
        with self._winner_card.canvas.before:
            Color(0.04, 0.06, 0.13, 0.95)
            self._wc_fill = RoundedRectangle(
                pos=self._winner_card.pos, size=self._winner_card.size,
                radius=[(16, 16)] * 4)
            self._wc_border_col = Color(*C_CYAN, 0.75)
            self._wc_border = Line(
                rounded_rectangle=(*self._winner_card.pos,
                                   *self._winner_card.size, 16),
                width=1.6)
        self._winner_card.bind(pos=self._sync_wc, size=self._sync_wc)

        self._winner_label = Label(
            text='WINNER', bold=True,
            size_hint=(1, 0.24), pos_hint={'center_x': 0.5, 'top': 0.96},
            color=(*C_DIM, 1), halign='center', valign='middle',
        )
        self._winner_name_lbl = Label(
            text='', bold=True,
            size_hint=(1, 0.44), pos_hint={'center_x': 0.5, 'center_y': 0.50},
            color=(*C_CYAN, 1), halign='center', valign='middle',
        )
        self._wins_lbl = Label(
            text='',
            size_hint=(1, 0.24), pos_hint={'center_x': 0.5, 'y': 0.04},
            color=(*C_DIM, 1), halign='center', valign='middle',
        )
        for lbl, frac in ((self._winner_label, 0.019),
                          (self._winner_name_lbl, 0.055),
                          (self._wins_lbl, 0.018)):
            self._scale(lbl, frac)
            lbl.bind(size=lbl.setter('text_size'))
            self._winner_card.add_widget(lbl)

        self._card_wrap.add_widget(self._winner_card)
        self._card_wrap.opacity = 0
        self._root.add_widget(self._card_wrap)

    def _build_table(self):
        self._table = FloatLayout(
            size_hint=(0.56, 0.36),
            pos_hint={'center_x': 0.5, 'center_y': 0.44},
            opacity=0,
        )

        header = BoxLayout(orientation='horizontal',
                           size_hint=(1, None),
                           pos_hint={'x': 0, 'top': 1.0})
        self._scale(header, 0.0, height_frac=0.045)
        for text, width in zip(('RANK', 'NAME', 'BEST TIME'), COL_W):
            lbl = Label(text=text, bold=True, size_hint_x=width,
                        color=(*C_ACCENT, 0.85),
                        halign='center', valign='middle')
            self._scale(lbl, 0.018)
            lbl.bind(size=lbl.setter('text_size'))
            header.add_widget(lbl)
        self._table.add_widget(header)

        with self._table.canvas.after:
            Color(*C_ACCENT, 0.30)
            self._rule = Rectangle(pos=(0, 0), size=(0, 1))
        self._table.bind(pos=self._sync_rule, size=self._sync_rule)
        header.bind(pos=self._sync_rule, size=self._sync_rule)

        scroll = ScrollView(
            size_hint=(1, 0.86), pos_hint={'x': 0, 'y': 0},
            do_scroll_x=False, bar_width=3,
            bar_color=(*C_ACCENT, 0.45),
        )
        self._rows = BoxLayout(orientation='vertical', size_hint_y=None,
                               spacing=2)
        self._rows.bind(minimum_height=self._rows.setter('height'))
        scroll.add_widget(self._rows)
        self._table.add_widget(scroll)
        self._root.add_widget(self._table)

    def _build_buttons(self):
        self._play_btn = self._make_btn(
            'PLAY AGAIN', C_ACCENT,
            {'center_x': 0.34, 'center_y': 0.14}, self._play_again)
        self._back_btn = self._make_btn(
            'MAIN MENU', C_MUTED,
            {'center_x': 0.66, 'center_y': 0.14}, self._go_home)
        for btn in (self._play_btn, self._back_btn):
            btn.opacity = 0
            self._root.add_widget(btn)

    def _make_btn(self, text, accent, pos_hint, callback):
        btn = Button(
            text=text, bold=True,
            size_hint=(0.20, 0.075), pos_hint=pos_hint,
            background_normal='', background_down='',
            background_color=(0, 0, 0, 0),
            color=(*accent, 1),
        )
        self._scale(btn, 0.022)
        with btn.canvas.before:
            Color(0.04, 0.06, 0.14, 0.90)
            fill = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[12])
            Color(*accent, 0.55)
            border = Line(rounded_rectangle=(*btn.pos, *btn.size, 12), width=1.4)
        def _sync(*_):
            fill.pos = btn.pos
            fill.size = btn.size
            border.rounded_rectangle = (*btn.pos, *btn.size, 12)
        btn.bind(pos=_sync, size=_sync, on_press=callback)
        return btn

    def _sync_bg(self, *_):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size

    def _sync_wc(self, *_):
        p, s = self._winner_card.pos, self._winner_card.size
        self._wc_fill.pos = p
        self._wc_fill.size = s
        self._wc_border.rounded_rectangle = (*p, *s, 16)

    def _sync_rule(self, *_):
        self._rule.pos = (self._table.x, self._table.top - self._table.height * 0.145)
        self._rule.size = (self._table.width, 1)

    def record_win(self, winner_name, winner_side, left_name, right_name,
                   match_time=None):
        self.winner_name = winner_name
        self.winner_side = winner_side
        self.last_match_time = match_time
        entry = {
            'winner': winner_name,
            'loser':  right_name if winner_side == 'left' else left_name,
            'side':   winner_side,
            'date':   datetime.now().strftime('%d %b %Y'),
            'time':   datetime.now().strftime('%H:%M'),
        }
        if match_time is not None:
            entry['seconds'] = round(match_time, 2)
        entries = _load()
        entries.append(entry)
        _save(entries)


    def on_pre_enter(self, *args):
        col = C_CYAN if self.winner_side == 'left' else C_PURPLE
        self._winner_name_lbl.color = (*col, 1)
        self._wc_border_col.rgba    = (*col, 0.75)
        self._winner_name_lbl.text  = self.winner_name.upper()

        entries = _load()
        wins = sum(1 for e in entries if e['winner'] == self.winner_name)
        secs = getattr(self, 'last_match_time', None)
        text = f'{wins} win{"s" if wins != 1 else ""} total'
        if secs is not None:
            text += f'   ·   {secs:.1f} s this match'
        self._wins_lbl.text = text

        self._table.opacity    = 0
        self._play_btn.opacity = 0
        self._back_btn.opacity = 0

        self._rescale()
        self._populate_history()
        self._card_wrap.opacity = 0

    def on_enter(self, *args):
        # let kivy finish the layout first
        Clock.schedule_once(self._pull_animation, 0.12)

    def _pull_animation(self, *_):
        wrap = self._card_wrap
        Animation.cancel_all(wrap)
        wrap.size    = self._root.size
        wrap.pos     = (0, self._root.height)
        wrap.opacity = 1
        anim = Animation(y=0, duration=0.72, t='out_back')
        anim.bind(on_complete=self._reveal_rest)
        anim.start(wrap)

    def _reveal_rest(self, *_):
        Animation(opacity=1, duration=0.40, t='out_quad').start(self._table)
        Clock.schedule_once(
            lambda *_: Animation(opacity=1, duration=0.35).start(self._play_btn), 0.18)
        Clock.schedule_once(
            lambda *_: Animation(opacity=1, duration=0.35).start(self._back_btn), 0.30)


    def _ranked(self):
        """Players by fastest recorded win; untimed legacy entries fall back
        to a wins ranking below the timed ones."""
        entries = _load()
        best = {}
        for e in entries:
            if 'seconds' in e:
                name = e.get('winner', '?')
                if name not in best or e['seconds'] < best[name]:
                    best[name] = e['seconds']
        ranked = [(name, f'{secs:.2f} s')
                  for name, secs in sorted(best.items(), key=lambda kv: kv[1])]
        # older saves only tracked wins
        legacy = Counter(e.get('winner', '?') for e in entries
                         if 'seconds' not in e)
        ranked += [(name, f'{count} win{"s" if count != 1 else ""}')
                   for name, count in legacy.most_common()
                   if name not in best]
        return ranked

    def _populate_history(self):
        self._row_scaled.clear()
        self._rows.clear_widgets()

        medals = (C_GOLD, C_SILVER, C_BRONZE)
        for i, (name, score) in enumerate(self._ranked()):
            colour = medals[i] if i < 3 else C_MUTED
            row = BoxLayout(orientation='horizontal', size_hint=(1, None))
            self._scale(row, 0.0, height_frac=0.042, row=True)
            cells = (
                (str(i + 1), C_DIM if i >= 3 else colour, 'center'),
                (name.upper(), colour, 'center'),
                (score, colour, 'center'),
            )
            for (text, col, align), width in zip(cells, COL_W):
                lbl = Label(text=text, bold=i < 3, size_hint_x=width,
                            color=(*col, 1), halign=align, valign='middle')
                self._scale(lbl, 0.023, row=True)
                lbl.bind(size=lbl.setter('text_size'))
                row.add_widget(lbl)
            self._rows.add_widget(row)

    def _play_again(self, *_):
        if self.manager:
            self.manager.current = 'BattleNameScreen'

    def _go_home(self, *_):
        if self.manager:
            self.manager.current = 'LandingScreen'
