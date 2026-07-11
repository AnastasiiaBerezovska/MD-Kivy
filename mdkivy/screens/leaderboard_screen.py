"""
LeaderboardScreen - shown after every BattleScreen win.

Winner card animates in from above (spring overshoot).
All positions are computed at animation time so root.size is always correct.
"""

import os, json
from datetime import datetime

from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.animation import Animation
from kivy.clock import Clock
from mdkivy.paths import FONT_IMPACT

_FONT    = FONT_IMPACT
from mdkivy.paths import LEADERBOARD_FILE as _LB_FILE

_CYAN   = (0.25, 0.80, 1.0, 1)
_PURPLE = (0.62, 0.38, 1.0, 1)


def _load():
    try:
        with open(_LB_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save(entries):
    try:
        with open(_LB_FILE, 'w') as f:
            json.dump(entries[-100:], f, indent=2)
    except Exception:
        pass


class LeaderboardScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.winner_name = ''
        self.winner_side = 'left'
        self._root = FloatLayout()
        self.add_widget(self._root)
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
            text='LEADERBOARD',
            font_name=_FONT, font_size=50,
            size_hint=(0.65, 0.10),
            pos_hint={'center_x': 0.5, 'top': 1.0},
            color=(1.0, 0.88, 0.20, 1),
            halign='center', valign='middle',
            outline_color=(0.6, 0.4, 0, 1), outline_width=3,
        )
        title.bind(size=title.setter('text_size'))
        self._root.add_widget(title)

        # -- winner card (manually sized & animated) --------------------
        self._winner_card = FloatLayout(size_hint=(None, None), size=(640, 190))
        with self._winner_card.canvas.before:
            Color(0.08, 0.06, 0.01, 0.97)
            self._wc_fill = RoundedRectangle(
                pos=self._winner_card.pos, size=self._winner_card.size,
                radius=[(18, 18)] * 4)
            Color(1.0, 0.88, 0.20, 1.0)
            self._wc_border = Line(
                rounded_rectangle=(*self._winner_card.pos,
                                   *self._winner_card.size, 18),
                width=2.6)
        self._winner_card.bind(pos=self._sync_wc, size=self._sync_wc)

        self._winner_label = Label(
            text='-- WINNER --',
            font_name=_FONT, font_size=17,
            size_hint=(1, 0.28),
            pos_hint={'center_x': 0.5, 'top': 1},
            color=(1.0, 0.80, 0.20, 0.75),
            halign='center', valign='middle',
        )
        self._winner_label.bind(size=self._winner_label.setter('text_size'))
        self._winner_card.add_widget(self._winner_label)

        self._winner_name_lbl = Label(
            text='',
            font_name=_FONT, font_size=46,
            size_hint=(1, 0.50),
            pos_hint={'center_x': 0.5, 'center_y': 0.46},
            color=(1, 1, 0.4, 1),
            halign='center', valign='middle',
            outline_color=(0.7, 0.5, 0, 1), outline_width=3,
        )
        self._winner_name_lbl.bind(size=self._winner_name_lbl.setter('text_size'))
        self._winner_card.add_widget(self._winner_name_lbl)

        self._wins_lbl = Label(
            text='',
            font_name=_FONT, font_size=17,
            size_hint=(1, 0.24),
            pos_hint={'center_x': 0.5, 'y': 0},
            color=(0.80, 0.80, 0.50, 0.80),
            halign='center', valign='middle',
        )
        self._wins_lbl.bind(size=self._wins_lbl.setter('text_size'))
        self._winner_card.add_widget(self._wins_lbl)

        # start off-screen so it doesn't flash on first add
        self._winner_card.pos = (-2000, -2000)
        self._root.add_widget(self._winner_card)

        # -- history panel ----------------------------------------------
        self._hist_panel = FloatLayout(
            size_hint=(0.72, 0.36),
            pos_hint={'center_x': 0.5, 'center_y': 0.36},
            opacity=0,
        )

        hist_title = Label(
            text='HALL OF FAME',
            font_name=_FONT, font_size=17,
            size_hint=(1, 0.10),
            pos_hint={'center_x': 0.5, 'top': 1.0},
            color=(0.55, 0.75, 1.0, 0.80),
            halign='center', valign='middle',
        )
        hist_title.bind(size=hist_title.setter('text_size'))
        self._hist_panel.add_widget(hist_title)

        # divider line under header
        with self._hist_panel.canvas.after:
            Color(0.30, 0.40, 0.70, 0.35)
            self._div = Rectangle(
                pos=(self._hist_panel.x, self._hist_panel.top - self._hist_panel.height * 0.11),
                size=(self._hist_panel.width, 1))
        self._hist_panel.bind(pos=self._sync_div, size=self._sync_div)

        scroll = ScrollView(
            size_hint=(1, 0.88),
            pos_hint={'x': 0, 'y': 0},
            do_scroll_x=False,
            bar_width=4,
            bar_color=(0.4, 0.6, 1, 0.5),
        )
        self._grid = GridLayout(
            cols=3,
            size_hint_y=None,
            spacing=[2, 4],
            padding=[4, 4],
        )
        self._grid.bind(minimum_height=self._grid.setter('height'))
        scroll.add_widget(self._grid)
        self._hist_panel.add_widget(scroll)
        self._root.add_widget(self._hist_panel)

        # -- bottom buttons ---------------------------------------------
        self._play_btn = self._make_btn(
            'PLAY AGAIN',
            fg=(1.0, 0.92, 0.30, 1),
            bg=(0.10, 0.08, 0.01, 1),
            bd=(1.0, 0.80, 0.15, 0.90),
            pos_hint={'center_x': 0.30, 'center_y': 0.07},
            callback=self._play_again,
        )
        self._back_btn = self._make_btn(
            'MAIN MENU',
            fg=(0.55, 0.85, 1.0, 1),
            bg=(0.03, 0.08, 0.20, 1),
            bd=(0.30, 0.60, 1.0, 0.80),
            pos_hint={'center_x': 0.70, 'center_y': 0.07},
            callback=self._go_home,
        )
        self._play_btn.opacity = 0
        self._back_btn.opacity = 0
        self._root.add_widget(self._play_btn)
        self._root.add_widget(self._back_btn)

    def _make_btn(self, text, fg, bg, bd, pos_hint, callback):
        btn = Button(
            text=text, font_name=_FONT, font_size=28,
            size_hint=(0.28, 0.10), pos_hint=pos_hint,
            background_normal='', background_color=(0, 0, 0, 0),
            color=fg,
        )
        with btn.canvas.before:
            Color(*bg)
            _bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[14])
            Color(*bd)
            _bd = Line(rounded_rectangle=(*btn.pos, *btn.size, 14), width=2.2)
        def _sync(*_):
            _bg.pos = btn.pos; _bg.size = btn.size
            _bd.rounded_rectangle = (*btn.pos, *btn.size, 14)
        btn.bind(pos=_sync, size=_sync, on_press=callback)
        return btn

    # ==================================================================
    # Sync helpers
    # ==================================================================

    def _sync_bg(self, *_):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size

    def _sync_wc(self, *_):
        p, s = self._winner_card.pos, self._winner_card.size
        self._wc_fill.pos = p;   self._wc_fill.size = s
        self._wc_border.rounded_rectangle = (*p, *s, 18)

    def _sync_div(self, *_):
        self._div.pos  = (self._hist_panel.x,
                          self._hist_panel.top - self._hist_panel.height * 0.11)
        self._div.size = (self._hist_panel.width, 1)

    # ==================================================================
    # Public API (called by BattleScreen before switching here)
    # ==================================================================

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

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def on_pre_enter(self, *args):
        col = _CYAN if self.winner_side == 'left' else _PURPLE
        self._winner_name_lbl.color = col
        self._winner_name_lbl.text  = self.winner_name.upper()
        self._wc_border.width = 2.6

        entries = _load()
        wc = sum(1 for e in entries if e['winner'] == self.winner_name)
        t  = getattr(self, 'last_match_time', None)
        wins_txt = f'{wc} win{"s" if wc != 1 else ""} total'
        if t is not None:
            wins_txt += f'  |  {t:.1f} s this match'
        self._wins_lbl.text = wins_txt

        # reset visibility
        self._hist_panel.opacity = 0
        self._play_btn.opacity   = 0
        self._back_btn.opacity   = 0

        self._populate_history()

        # hide card off-screen - position computed properly in _pull_animation
        self._winner_card.pos = (-2000, -2000)

    def on_enter(self, *args):
        # small delay lets the layout settle so root.size is correct
        Clock.schedule_once(self._pull_animation, 0.12)

    def _pull_animation(self, *_):
        rw = self._root.width
        rh = self._root.height

        # size card proportionally to the actual window
        cw = min(rw * 0.55, 700)
        ch = max(rh * 0.22, 155)
        self._winner_card.size = (cw, ch)

        # target: centered horizontally, upper area (card center at 74% from bottom)
        tx = (rw - cw) / 2
        ty = rh * 0.74 - ch / 2

        # start above the screen, then spring down
        self._winner_card.pos = (tx, rh + 20)

        Animation.cancel_all(self._winner_card)
        anim = Animation(x=tx, y=ty, duration=0.72, t='out_back')
        anim.bind(on_complete=self._reveal_rest)
        anim.start(self._winner_card)

    def _reveal_rest(self, *_):
        Animation(opacity=1, duration=0.40, t='out_quad').start(self._hist_panel)
        Clock.schedule_once(
            lambda *_: Animation(opacity=1, duration=0.35).start(self._play_btn), 0.18)
        Clock.schedule_once(
            lambda *_: Animation(opacity=1, duration=0.35).start(self._back_btn), 0.30)

    # ==================================================================
    # History grid
    # ==================================================================

    def _populate_history(self):
        self._grid.clear_widgets()

        # Column headers: RANK | NAME | BEST TIME (fastest to the target wins)
        headers = [
            ('#',         (1.0, 0.85, 0.20, 0.80)),
            ('NAME',      (1.0, 0.85, 0.20, 0.80)),
            ('BEST TIME', (1.0, 0.85, 0.20, 0.80)),
        ]
        for txt, col in headers:
            lbl = Label(text=txt, font_name=_FONT, font_size=15,
                        size_hint_y=None, height=32,
                        color=col, halign='center', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            self._grid.add_widget(lbl)

        # Rank players by their fastest recorded win; untimed legacy
        # entries fall back to a wins ranking at the bottom of the list.
        from collections import Counter
        entries = _load()
        best = {}
        for e in entries:
            if 'seconds' in e:
                name = e.get('winner', '?')
                if name not in best or e['seconds'] < best[name]:
                    best[name] = e['seconds']
        ranked = [(name, f'{secs:.1f} s')
                  for name, secs in sorted(best.items(), key=lambda kv: kv[1])]
        legacy = Counter(e.get('winner', '?') for e in entries
                         if 'seconds' not in e)
        ranked += [(name, f'{count} win{"s" if count != 1 else ""}')
                   for name, count in legacy.most_common()
                   if name not in best]

        rank_colours = [
            (1.0, 0.85, 0.15, 1.0),   # gold   - 1st
            (0.80, 0.80, 0.80, 1.0),  # silver - 2nd
            (0.85, 0.50, 0.20, 1.0),  # bronze - 3rd
        ]
        for i, (name, count) in enumerate(ranked):
            rank_num = i + 1
            if rank_num <= 3:
                name_col  = rank_colours[i]
                count_col = rank_colours[i]
                rank_txt  = ['1st', '2nd', '3rd'][i]
            else:
                name_col  = (0.70, 0.70, 0.75, 1.0)
                count_col = (0.60, 0.60, 0.65, 1.0)
                rank_txt  = f'{rank_num}th'

            for txt, col in [(rank_txt, (0.50, 0.50, 0.60, 0.85)),
                             (name,     name_col),
                             (count,    count_col)]:
                lbl = Label(text=txt, font_name=_FONT, font_size=14,
                            size_hint_y=None, height=28,
                            color=col, halign='center', valign='middle')
                lbl.bind(size=lbl.setter('text_size'))
                self._grid.add_widget(lbl)

    # ==================================================================
    # Navigation
    # ==================================================================

    def _play_again(self, *_):
        if self.manager:
            self.manager.current = 'BattleNameScreen'

    def _go_home(self, *_):
        if self.manager:
            self.manager.current = 'LandingScreen'
