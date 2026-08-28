"""Two-player molecular temperature battle."""

import os, math, random, time
from kivy.uix.screenmanager import Screen
from mdkivy.inputs.dual_makey import DualMakeyInput
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import (Color, Ellipse, Rectangle, Line,
                            RoundedRectangle)
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.properties import NumericProperty
from kivy.uix.image import Image
from mdkivy.paths import FONT_IMPACT, TAP_ICON, STOMP_ICON

_FONT   = FONT_IMPACT

TEMP_TARGET     = 373.15
SPAWN_SPEED     = 300.0
GRAVITY         = 0.0
WALL_RESTITUTION= 1.0
MOL_R_RATIO     = 0.022
MAX_MOLS_SIDE   = 40
PHYSICS_DT      = 1/30.0
DRAW_DT         = 1/30.0
HUD_DT          = 0.25
SPAWN_COOLDOWN  = 0.12
MAX_SPEED       = 550.0

R_GAS       = 8.314
AVOGADRO    = 6.022e23
SIDE_VOLUME = 4.88

INTRO_FADE_IN  = 0.80
INTRO_HOLD     = 1.00
INTRO_FADE_OUT = 1.40

C_PRESSURE  = (0.31, 0.76, 0.97)
C_VOLUME    = (1.00, 0.62, 0.25)
C_MOLES     = (0.89, 0.28, 0.78)
C_RGAS      = (0.66, 0.85, 0.29)
C_OPER      = (0.55, 0.55, 0.62)
C_TARGET    = (0.94, 0.25, 0.48)
C_WATERMARK = (0.52, 0.13, 0.19)
C_INTRO     = (0.36, 0.78, 0.96)


class BattleScreen(Screen):

    hud_reveal = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._molecules       = []
        self._divider_alive   = True
        self._winner          = None
        self._state           = 'idle'
        self._left_name       = 'Player 1'
        self._right_name      = 'Player 2'
        self._lb_ev           = None
        self._phy_ev          = None
        self._drw_ev          = None
        self._hud_ev          = None
        self._divider_opacity = 1.0
        self._flash_opacity   = 0.0
        self._shards          = []
        self._pops            = []

        self._last_spawn = {'left': 0.0, 'right': 0.0}
        self._wm_cache        = {}
        self._reveal_ev       = None
        self._font_scaled     = []
        self._root = FloatLayout()
        self.add_widget(self._root)

        self._build_backgrounds()
        self._build_arena()
        self._build_equation_panels()
        self._build_target_panel()
        self._build_name_labels()
        self._build_win_label()
        self._build_back_button()
        self._build_intro_overlay()
        Window.bind(on_resize=self._rescale_fonts)


    @property
    def _mol_radius(self):
        """Molecule radius tracks the arena so molecules keep the same
        apparent size whatever the display resolution."""
        return max(6.0, self._arena.height * MOL_R_RATIO)

    def _scale_font(self, widget, frac, outline=0.0):
        """Track font size as a fraction of window height.

        Fixed pixel sizes look right in a windowed session and shrink to
        nothing full-screen on the exhibit display, so every label registers
        here and gets resized whenever the window does.
        """
        self._font_scaled.append((widget, frac, outline))
        self._apply_font(widget, frac, outline)
        return widget

    @staticmethod
    def _apply_font(widget, frac, outline):
        widget.font_size = max(9.0, Window.height * frac)
        if outline:
            widget.outline_width = max(1, int(Window.height * outline))

    def _rescale_fonts(self, *_):
        for widget, frac, outline in self._font_scaled:
            self._apply_font(widget, frac, outline)

    def _build_backgrounds(self):
        with self._root.canvas.before:
            Color(0.01, 0.02, 0.06, 1)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_):
        self._bg.pos  = self._root.pos
        self._bg.size = self._root.size

    def _build_target_panel(self):
        """Goal readout, centred on the divider."""
        self._target_sub = Label(
            text='First to',
            bold=True,
            halign='center', valign='bottom',
            color=(*C_TARGET, 0.95),
            size_hint=(0.16, 0.05),
            pos_hint={'center_x': 0.5, 'center_y': 0.545},
        )
        self._target_lbl = Label(
            text=f'{TEMP_TARGET:g} Kelvin',
            bold=True,
            halign='center', valign='top',
            color=(*C_TARGET, 1),
            size_hint=(0.16, 0.06),
            pos_hint={'center_x': 0.5, 'center_y': 0.495},
        )
        for lbl, frac in ((self._target_sub, 0.019), (self._target_lbl, 0.027)):
            self._scale_font(lbl, frac)
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

    def _build_equation_panels(self):
        """T = PV / nR above each half, one colour per term."""
        self._eq_vals = {}
        for team, cx in (('left', 0.262), ('right', 0.738)):
            row = BoxLayout(
                orientation='horizontal',
                size_hint=(0.40, 0.075),
                pos_hint={'center_x': cx, 'top': 0.945},
                spacing=dp(2),
            )
            for child in (
                self._eq_bracket('('),
                self._eq_term(team, 'pressure'),
                self._eq_oper('\u00d7', 0.30),
                self._eq_term(team, 'volume'),
                self._eq_bracket(')'),
                self._eq_oper('\u00f7', 0.42),
                self._eq_bracket('('),
                self._eq_term(team, 'moles'),
                self._eq_oper('\u00d7', 0.30),
                self._eq_term(team, 'rgas'),
                self._eq_bracket(')'),
            ):
                row.add_widget(child)
            self._root.add_widget(row)

    def _eq_bracket(self, ch):
        """Tall thin bracket spanning the full panel height."""
        lbl = self._scale_font(
            Label(text=ch, color=(*C_OPER, 0.70),
                  size_hint_x=0.30, halign='center', valign='middle'), 0.054)
        lbl.bind(size=lbl.setter('text_size'))
        return lbl

    def _eq_oper(self, ch, width):
        """Operator, dropped to sit on the value row rather than centred."""
        box = BoxLayout(orientation='vertical', size_hint_x=width)
        lbl = self._scale_font(
            Label(text=ch, bold=True, color=(*C_OPER, 0.95),
                  size_hint_y=0.58, halign='center', valign='top'), 0.021)
        lbl.bind(size=lbl.setter('text_size'))
        box.add_widget(Widget(size_hint_y=0.42))
        box.add_widget(lbl)
        return box

    _EQ_TERMS = {
        'pressure': ('Pressure',     C_PRESSURE, 1.00),
        'volume':   ('Volume',       C_VOLUME,   0.95),
        'moles':    ('Moles',        C_MOLES,    1.05),
        'rgas':     ('Gas Constant', C_RGAS,     1.35),
    }

    def _eq_term(self, team, key):
        """One named term: label above, live value below."""
        name, colour, width = self._EQ_TERMS[key]
        box = BoxLayout(orientation='vertical', size_hint_x=width)
        nm = self._scale_font(
            Label(text=name, bold=True, color=(*colour, 1),
                  size_hint_y=0.42, halign='center', valign='bottom'), 0.015)
        val = self._scale_font(
            Label(text='0', bold=True, markup=True, color=(*colour, 1),
                  size_hint_y=0.58, halign='center', valign='top'), 0.028)
        for lbl in (nm, val):
            lbl.bind(size=lbl.setter('text_size'))
            box.add_widget(lbl)
        self._eq_vals[(team, key)] = val
        return box

    @staticmethod
    def _sci(v):
        """Readable numbers stay plain; very small ones go to x10^n markup."""
        if v <= 0:
            return '0'
        exp = int(math.floor(math.log10(v)))
        if -2 <= exp <= 3:
            return f'{v:.2f}'
        return f'{v / 10 ** exp:.0f}\u00d710[sup]{exp}[/sup]'

    def _update_equation(self, team, temp):
        n = len([m for m in self._molecules if m['team'] == team]) / AVOGADRO
        p = n * R_GAS * temp / SIDE_VOLUME
        for key, text in (('pressure', self._sci(p)),
                          ('volume',   f'{SIDE_VOLUME:g}'),
                          ('moles',    self._sci(n)),
                          ('rgas',     f'{R_GAS:g}')):
            lbl = self._eq_vals.get((team, key))
            if lbl is not None and lbl.text != text:
                lbl.text = text

    def _build_win_label(self):
        """Winner banner - small label over a large value, the same shape the
        target readout and the equation panel already use."""
        self._win_sub = Label(
            text='WINNER', bold=True,
            size_hint=(0.5, 0.05),
            pos_hint={'center_x': 0.5, 'center_y': 0.585},
            halign='center', valign='bottom',
            opacity=0,
        )
        self._win_lbl = Label(
            text='', bold=True,
            size_hint=(0.7, 0.11),
            pos_hint={'center_x': 0.5, 'center_y': 0.515},
            halign='center', valign='top',
            opacity=0,
        )
        for lbl, frac in ((self._win_sub, 0.021), (self._win_lbl, 0.075)):
            self._scale_font(lbl, frac)
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

    def _build_back_button(self):
        btn = Button(
            text='BACK', font_name=_FONT,
            size_hint=(0.055, 0.036),
            pos_hint={'x': 0.008, 'y': 0.958},
            background_normal='', background_color=(0, 0, 0, 0),
            color=(0.55, 0.75, 1.0, 1),
        )
        with btn.canvas.before:
            Color(0.04, 0.10, 0.22, 0.92)
            _bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[6])
            Color(0.30, 0.60, 1.0, 0.65)
            _bd = Line(rounded_rectangle=(*btn.pos, *btn.size, 6), width=1.2)
        def _sync(*_):
            _bg.pos = btn.pos; _bg.size = btn.size
            _bd.rounded_rectangle = (*btn.pos, *btn.size, 6)
        self._scale_font(btn, 0.016)
        btn.bind(pos=_sync, size=_sync, on_press=lambda *_: self._go_back())
        self._root.add_widget(btn)

    def _build_arena(self):
        """The main play area - a widget whose canvas we redraw each frame."""
        self._arena = FloatLayout(
            size_hint=(0.96, 0.878),
            pos_hint={'center_x': 0.5, 'top': 0.952},
        )
        self._root.add_widget(self._arena)

    def _build_name_labels(self):
        """Small name plates in the bottom corner of each half."""
        self._left_name_lbl = Label(
            text=self._left_name,
            font_name=_FONT,
            size_hint=(0.30, 0.06),
            pos_hint={'center_x': 0.26, 'y': 0.075},
            halign='center', valign='middle',
            color=(0.25, 0.80, 1.0, 0.80),
        )
        self._right_name_lbl = Label(
            text=self._right_name,
            font_name=_FONT,
            size_hint=(0.30, 0.06),
            pos_hint={'center_x': 0.74, 'y': 0.075},
            halign='center', valign='middle',
            color=(0.62, 0.38, 1.0, 0.80),
        )
        for lbl in (self._left_name_lbl, self._right_name_lbl):
            self._scale_font(lbl, 0.030)
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)


    def _build_intro_overlay(self):
        """How-to-play cues shown for three seconds before the match starts."""
        self._intro = FloatLayout(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0},
                                  opacity=0)
        rows = (
            (TAP_ICON,   'Add Molecules',              0.613, 0.196, 0.20),
            (STOMP_ICON, 'Remove Opponent\nMolecules', 0.424, 0.189, 0.16),
        )
        for source, text, cy, text_x, text_w in rows:
            for dx in (0.0, 0.5):
                icon = Image(source=source, fit_mode='contain',
                             size_hint=(0.075, 0.115),
                             pos_hint={'center_x': 0.139 + dx, 'center_y': cy})
                self._intro.add_widget(icon)
                lbl = Label(text=text, bold=True,
                            color=(*C_INTRO, 1),
                            size_hint=(text_w, 0.11),
                            pos_hint={'x': text_x + dx, 'center_y': cy},
                            halign='left', valign='middle')
                self._scale_font(lbl, 0.025)
                lbl.bind(size=lbl.setter('text_size'))
                self._intro.add_widget(lbl)
        self._root.add_widget(self._intro)

    def _run_intro(self):
        """Fade the cues in, hold, then dissolve them into the live readout."""
        Animation.cancel_all(self._intro)
        Animation.cancel_all(self)
        if self._reveal_ev:
            self._reveal_ev.cancel()
        self._intro.opacity = 0
        self.hud_reveal     = 0.0

        seq = (Animation(opacity=1, duration=INTRO_FADE_IN, t='out_sine')
               + Animation(duration=INTRO_HOLD)
               + Animation(opacity=0, duration=INTRO_FADE_OUT, t='in_out_sine'))
        seq.bind(on_complete=lambda *_: self._begin_match())
        seq.start(self._intro)

        def _reveal(_dt):
            Animation(hud_reveal=1.0, duration=INTRO_FADE_OUT,
                      t='in_out_sine').start(self)
        self._reveal_ev = Clock.schedule_once(
            _reveal, INTRO_FADE_IN + INTRO_HOLD)

    def _begin_match(self):
        if self._state == 'intro':
            self._state       = 'playing'
            self._match_start = time.monotonic()


    def on_enter(self, *args):
        self._rescale_fonts()
        self._left_name_lbl.text  = self._left_name
        self._right_name_lbl.text = self._right_name
        self._reset()
        # don't carry the battle button tap into the arena
        self._touch_ready = False
        Clock.schedule_once(lambda *_: setattr(self, '_touch_ready', True), 0.5)
        self._run_intro()
        self._phy_ev = Clock.schedule_interval(self._physics, PHYSICS_DT)
        self._drw_ev = Clock.schedule_interval(self._draw,    DRAW_DT)
        self._hud_ev = Clock.schedule_interval(self._hud_tick, HUD_DT)
        self._dual_makey = DualMakeyInput(
            left_cb=lambda: self._remove_mol('right'),
            right_cb=lambda: self._remove_mol('left'),
        )
        Window.unbind(on_key_down=self._key_down)
        Window.bind(on_key_down=self._key_down)

    def on_pre_leave(self, *args):
        Window.unbind(on_key_down=self._key_down)
        Animation.cancel_all(self._intro)
        Animation.cancel_all(self)
        if self._reveal_ev:
            self._reveal_ev.cancel()
            self._reveal_ev = None
        if getattr(self, '_dual_makey', None):
            self._dual_makey.stop()
            self._dual_makey = None
        for ev in (self._phy_ev, self._drw_ev, self._hud_ev,
                   getattr(self, '_tgt_pulse_ev', None),
                   getattr(self, '_lb_ev', None)):
            if ev:
                ev.cancel()
        self._phy_ev = self._drw_ev = self._hud_ev = self._lb_ev = None
        self._molecules.clear()
        self._shards.clear()
        self._pops.clear()
        self._arena.canvas.clear()

    def _go_back(self):
        if self.manager:
            self.manager.current = 'LandingScreen'

    def _go_to_leaderboard(self, *_):
        if not self.manager:
            return
        winner_name = self._left_name if self._winner == 'left' else self._right_name
        lb = self.manager.get_screen('LeaderboardScreen')
        lb.record_win(winner_name, self._winner, self._left_name, self._right_name,
                      match_time=self._match_time)
        self.manager.current = 'LeaderboardScreen'

    def _reset(self):
        self._molecules.clear()
        self._shards            = []
        self._pops              = []
        self._divider_alive     = True
        self._divider_opacity   = 1.0
        self._flash_opacity     = 0.0
        self._winner            = None
        self._state             = 'intro'
        self._match_start       = time.monotonic()
        self._match_time        = None
        self._last_spawn   = {'left': 0.0, 'right': 0.0}
        self._win_lbl.text = ''
        for lbl in (self._win_sub, self._win_lbl):
            Animation.cancel_all(lbl)
            lbl.opacity = 0
        for lbl in (self._target_sub, self._target_lbl):
            Animation.cancel_all(lbl)
            lbl.opacity = 1


    def _key_down(self, window, key, scancode, codepoint, modifiers):
        # makeys are already handled by evdev
        if getattr(self, '_dual_makey', None) and self._dual_makey._devices:
            return
        if self._state != 'playing':
            return
        if key in (276, 97, 32):
            self._remove_mol('right')
        elif key in (275, 108, 13, 271):
            self._remove_mol('left')

    def _spawn(self, team):
        a = self._arena
        if a.width < 10:
            return

        mid = a.x + a.width / 2
        r   = self._mol_radius

        side_mols = [m for m in self._molecules if m['team'] == team]
        if len(side_mols) >= MAX_MOLS_SIDE:
            return

        x  = mid
        y  = a.y + a.height / 2
        if team == 'left':
            vx = -random.uniform(SPAWN_SPEED * 0.55, SPAWN_SPEED * 0.85)
        else:
            vx = random.uniform(SPAWN_SPEED * 0.55, SPAWN_SPEED * 0.85)
        vy = random.uniform(-SPAWN_SPEED * 0.5, SPAWN_SPEED * 0.5)

        self._molecules.append({
            'x': x, 'y': y,
            'vx': vx, 'vy': vy,
            'team': team,
        })

    def _remove_mol(self, team):
        """Remove a random molecule from the team and play a bubble-pop animation."""
        side = [m for m in self._molecules if m['team'] == team]
        if not side:
            return
        m = random.choice(side)
        self._molecules.remove(m)
        cr, cg, cb = (0.16, 0.50, 0.95) if team == 'left' else (0.48, 0.20, 0.90)
        life = 0.50
        self._pops.append({
            'x': m['x'], 'y': m['y'],
            'r': self._mol_radius * 0.3,
            'max_r': self._mol_radius * 4.0,
            'life': life, 'max_life': life,
            'cr': cr, 'cg': cg, 'cb': cb,
            'droplets': [
                {
                    'dx': 0.0, 'dy': 0.0,
                    'vx': random.uniform(80, 160) * math.cos(a),
                    'vy': random.uniform(80, 160) * math.sin(a),
                }
                for a in (i * math.pi / 4 for i in range(8))
            ],
        })

    def _spawn_at(self, x, y, team):
        """Spawn one molecule at the exact touch position. No energy kick."""
        a = self._arena
        if a.width < 10 or self._state != 'playing':
            return
        if len([m for m in self._molecules if m['team'] == team]) >= MAX_MOLS_SIDE:
            return
        mid = a.x + a.width / 2
        r   = self._mol_radius
        if team == 'left':
            x = max(a.x + r, min(x, mid - r))
        else:
            x = max(mid + r, min(x, a.x + a.width - r))
        y = max(a.y + r, min(y, a.y + a.height - r))
        angle = random.uniform(0, math.pi * 2)
        spd   = SPAWN_SPEED * random.uniform(0.8, 1.0)
        self._molecules.append({
            'x': x, 'y': y,
            'vx': spd * math.cos(angle),
            'vy': spd * math.sin(angle),
            'team': team,
        })

    def on_touch_down(self, touch):
        """Spawn on the tapped side.

        The device='mouse' event carries the calibrated cursor position; the
        raw touch device is mis-mapped, so only mouse events spawn.
        """
        if getattr(touch, 'multitouch_sim', False):
            return True
        if getattr(touch, 'device', '') != 'mouse':
            return True
        if getattr(touch, 'button', 'left') != 'left':
            return True
        if touch.grab_current is not None:
            return True
        if not getattr(self, '_touch_ready', False):
            return True
        if self._state != 'playing':
            return super().on_touch_down(touch)

        px, py = touch.pos
        a = self._arena
        if a.height > 10:
            in_arena_y = a.y <= py <= a.y + a.height
        else:
            in_arena_y = Window.height * 0.16 <= py <= Window.height * 0.88
        if not in_arena_y:
            return super().on_touch_down(touch)

        win_mid = Window.width / 2
        # leave a no-spawn strip down the middle
        dead    = Window.width * 0.05

        if px < win_mid - dead:
            team = 'left'
        elif px > win_mid + dead:
            team = 'right'
        else:
            return True

        now = Clock.get_time()
        if now - self._last_spawn[team] >= SPAWN_COOLDOWN:
            self._last_spawn[team] = now
            self._spawn_at(px, py, team)
        return True


    def _physics(self, dt):
        if self._state == 'idle':
            return
        a   = self._arena
        if a.width < 10:
            return
        ax, ay, aw, ah = a.x, a.y, a.width, a.height
        mid = ax + aw / 2
        r   = self._mol_radius
        mols = self._molecules

        for m in mols:
            m['vy'] -= GRAVITY * dt
            m['x']  += m['vx'] * dt
            m['y']  += m['vy'] * dt

            if m['y'] - r < ay:
                m['y'] = ay + r
                m['vy'] = abs(m['vy']) * WALL_RESTITUTION
            if m['y'] + r > ay + ah:
                m['y'] = ay + ah - r
                m['vy'] = -abs(m['vy']) * WALL_RESTITUTION

            if m['x'] - r < ax:
                m['x'] = ax + r
                m['vx'] = abs(m['vx']) * WALL_RESTITUTION
            if m['x'] + r > ax + aw:
                m['x'] = ax + aw - r
                m['vx'] = -abs(m['vx']) * WALL_RESTITUTION

            if self._divider_alive:
                if m['team'] == 'left' and m['x'] + r > mid:
                    m['x'] = mid - r
                    m['vx'] = -abs(m['vx']) * 0.88
                elif m['team'] == 'right' and m['x'] - r < mid:
                    m['x'] = mid + r
                    m['vx'] = abs(m['vx']) * 0.88

        min_d = r * 2
        for i in range(len(mols)):
            for j in range(i + 1, len(mols)):
                m1, m2 = mols[i], mols[j]
                dx = m2['x'] - m1['x']
                dy = m2['y'] - m1['y']
                # cheap check before the distance math
                if abs(dx) > min_d or abs(dy) > min_d:
                    continue
                d2 = dx*dx + dy*dy
                if d2 < min_d * min_d and d2 > 0:
                    d   = d2 ** 0.5
                    nx  = dx / d;  ny = dy / d
                    ovr = (min_d - d) * 0.5
                    m1['x'] -= nx * ovr;  m1['y'] -= ny * ovr
                    m2['x'] += nx * ovr;  m2['y'] += ny * ovr
                    v1n = m1['vx']*nx + m1['vy']*ny
                    v2n = m2['vx']*nx + m2['vy']*ny
                    m1['vx'] += (v2n - v1n) * nx
                    m1['vy'] += (v2n - v1n) * ny
                    m2['vx'] += (v1n - v2n) * nx
                    m2['vy'] += (v1n - v2n) * ny

        for m in mols:
            spd = (m['vx']**2 + m['vy']**2) ** 0.5
            # keep repeated kicks sane
            if spd > MAX_SPEED:
                s = MAX_SPEED / spd
                m['vx'] *= s
                m['vy'] *= s

        if self._flash_opacity > 0:
            self._flash_opacity = max(0.0, self._flash_opacity - 3.5 * dt)

        for s in self._shards:
            s['x']    += s['vx'] * dt
            s['y']    += s['vy'] * dt
            s['vy']   -= GRAVITY * 3 * dt
            s['life'] -= dt
        self._shards = [s for s in self._shards if s['life'] > 0]

        for p in self._pops:
            frac    = 1.0 - p['life'] / p['max_life']
            p['r']  = p['max_r'] * frac
            for d in p['droplets']:
                d['dx'] += d['vx'] * dt
                d['dy'] += d['vy'] * dt
            p['life'] -= dt
        self._pops = [p for p in self._pops if p['life'] > 0]


    def _hud_tick(self, *_):
        if self._state == 'playing':
            self._check_win()
        else:
            for team in ('left', 'right'):
                self._update_equation(team, self._side_thermal(team))

    @staticmethod
    def _speed(m):
        return (m['vx']**2 + m['vy']**2) ** 0.5

    def _avg_temp(self, team):
        """T = average KE per molecule = <v²>/2, scaled /1000 for display.
        Obeys PV=nRT: P ∝ nT (V fixed, R=1)."""
        side = [m for m in self._molecules if m['team'] == team]
        if not side:
            return 0.0
        return sum(m['vx']**2 + m['vy']**2 for m in side) / (len(side) * 2000.0)

    def _side_thermal(self, team):
        """Temperature-like reading for one side: total KE / 1000.
        Grows with both molecule count and speed, so spawning faster
        heats the side toward TEMP_TARGET sooner."""
        return sum(m['vx']**2 + m['vy']**2
                   for m in self._molecules if m['team'] == team) / 2000.0

    def _pressure(self, team):
        """P = nRT/V - V fixed so P ∝ n*T."""
        n = sum(1 for m in self._molecules if m['team'] == team)
        return n * self._avg_temp(team)

    def _check_win(self):
        tl = self._side_thermal('left')
        tr = self._side_thermal('right')

        self._update_equation('left',  tl)
        self._update_equation('right', tr)

        if tl >= TEMP_TARGET and self._winner is None:
            self._trigger_win('left')
        elif tr >= TEMP_TARGET and self._winner is None:
            self._trigger_win('right')

    def _trigger_win(self, winner):
        self._winner = winner
        self._state  = 'breaking'
        if getattr(self, '_match_start', None):
            self._match_time = time.monotonic() - self._match_start

        winner_name = self._left_name if winner == 'left' else self._right_name
        col = (0.25, 0.80, 1.0) if winner == 'left' else (0.62, 0.38, 1.0)

        self._win_lbl.text  = winner_name.upper()
        self._win_lbl.color = (*col, 1)
        self._win_sub.color = (*col, 0.70)
        for lbl in (self._win_sub, self._win_lbl):
            Animation.cancel_all(lbl)
            lbl.opacity = 0
            Animation(opacity=1, duration=0.5, t='out_cubic').start(lbl)

        for lbl in (self._target_sub, self._target_lbl):
            Animation(opacity=0, duration=0.35, t='out_sine').start(lbl)
        Animation(hud_reveal=0.22, duration=0.5, t='out_sine').start(self)

        def _fade_div(dt):
            self._divider_opacity = max(0.0, self._divider_opacity - 0.18)
            if self._divider_opacity <= 0:
                self._divider_alive   = False
                self._flash_opacity   = 1.0
                self._divider_opacity = 0.0
                self._start_flood()
                return False
        Clock.schedule_interval(_fade_div, 0.03)
        self._lb_ev = Clock.schedule_once(self._go_to_leaderboard, 4.0)

    def _start_flood(self):
        self._state  = 'flooding'
        a            = self._arena
        mid          = a.x + a.width / 2
        ay, ah       = a.y, a.height
        toward_winner = -1 if self._winner == 'left' else 1

        for _ in range(28):
            y     = random.uniform(ay, ay + ah)
            angle = random.uniform(0, math.pi * 2)
            spd   = random.uniform(120, 480)
            self._shards.append({
                'x': mid, 'y': y,
                'vx': spd * math.cos(angle),
                'vy': spd * math.sin(angle),
                'size': random.uniform(0.25, 0.70) * self._mol_radius,
                'life': random.uniform(0.25, 0.75),
            })

        for m in self._molecules:
            if m['team'] == self._winner:
                m['vx'] = -toward_winner * random.uniform(500, 900)
                m['vy'] = random.uniform(-250, 250)
            else:
                m['vx'] = -toward_winner * random.uniform(150, 350)
                m['vy'] = random.uniform(-150, 150)


    def _watermark(self, team, text, height):
        """Cached CoreLabel texture for the big temperature readout."""
        size = max(12, int(height))
        cached = self._wm_cache.get(team)
        if cached is None or cached[0] != (text, size):
            core = CoreLabel(text=text, font_size=size, bold=True)
            core.refresh()
            cached = ((text, size), core.texture)
            self._wm_cache[team] = cached
        return cached[1]

    def _draw(self, dt):
        a = self._arena
        if a.width < 10:
            return

        ax, ay, aw, ah = a.x, a.y, a.width, a.height
        mid = ax + aw / 2
        r   = self._mol_radius

        c = a.canvas
        c.clear()
        with c:
            Color(0.02, 0.025, 0.06, 1)
            Rectangle(pos=(ax, ay), size=(aw, ah))

            Color(0.20, 0.35, 0.62, 0.40)
            Line(rectangle=(ax, ay, aw, ah), width=1.4)

            for team, cx in (('left', ax + aw * 0.25), ('right', ax + aw * 0.75)):
                tex = self._watermark(team, f'{self._side_thermal(team):.1f} K',
                                      ah * 0.14)
                Color(*C_WATERMARK, 0.60 * self.hud_reveal)
                Rectangle(texture=tex,
                          pos=(cx - tex.width / 2, ay + ah * 0.5 - tex.height / 2),
                          size=tex.size)

            if self._divider_opacity > 0.01:
                op   = self._divider_opacity
                core = max(3.0, ah * 0.0055)
                lo = self._target_lbl.y   - ah * 0.030
                hi = self._target_sub.top + ah * 0.030
                spans = ([(ay, lo), (hi, ay + ah)]
                         if ay < lo < hi < ay + ah else [(ay, ay + ah)])
                for y0, y1 in spans:
                    Color(0.45, 0.92, 1.0, 0.06 * op)
                    Line(points=[mid, y0, mid, y1], width=core * 6)
                    Color(0.50, 0.93, 1.0, 0.18 * op)
                    Line(points=[mid, y0, mid, y1], width=core * 3)
                    Color(0.62, 0.97, 1.0, 0.85 * op)
                    Line(points=[mid, y0, mid, y1], width=core)

            if self._flash_opacity > 0.01:
                fo = self._flash_opacity
                inner = max(40.0, aw * 0.035)
                outer = max(95.0, aw * 0.082)
                Color(1.0, 1.0, 1.0, fo * 0.55)
                Rectangle(pos=(mid - inner, ay), size=(inner * 2, ah))
                Color(1.0, 0.95, 0.7, fo * 0.30)
                Rectangle(pos=(mid - outer, ay), size=(outer * 2, ah))

            for s in self._shards:
                alpha = max(0.0, s['life'] * 1.8)
                Color(0.55, 0.95, 1.0, min(alpha, 0.9))
                sz = s['size']
                Rectangle(pos=(s['x'] - sz/2, s['y'] - sz/2), size=(sz, sz))

            for p in self._pops:
                frac  = 1.0 - p['life'] / p['max_life']
                alpha = max(0.0, 1.0 - frac)
                cr2, cg2, cb2 = p['cr'], p['cg'], p['cb']
                if p['r'] > 1:
                    Color(cr2, cg2, cb2, alpha * 0.90)
                    Line(circle=(p['x'], p['y'], p['r']), width=2.8)
                ir = p['r'] * 0.55
                if ir > 1:
                    Color(1.0, 1.0, 1.0, alpha * 0.55)
                    Line(circle=(p['x'], p['y'], ir), width=1.4)
                dr = max(1.5, r * 0.28 * alpha)
                for d in p['droplets']:
                    Color(cr2, cg2, cb2, alpha * 0.80)
                    Ellipse(pos=(p['x']+d['dx']-dr, p['y']+d['dy']-dr),
                            size=(dr*2, dr*2))

            for m in self._molecules:
                mx, my = m['x'], m['y']
                spd  = self._speed(m)
                heat = min(spd / SPAWN_SPEED, 1.0)

                if m['team'] == 'left':
                    cr, cg, cb = 0.02 + 0.18*heat, 0.07 + 0.28*heat, 0.50 + 0.38*heat
                else:
                    cr, cg, cb = 0.36 + 0.28*heat, 0.20 + 0.24*heat, 0.58 + 0.30*heat

                gr = r * 1.55
                Color(cr, cg, cb, 0.16)
                Ellipse(pos=(mx-gr, my-gr), size=(gr*2, gr*2))
                Color(cr*0.35, cg*0.35, cb*0.45, 1)
                Ellipse(pos=(mx-r, my-r), size=(r*2, r*2))
                Color(cr, cg, cb, 1)
                mr2 = r * 0.82
                Ellipse(pos=(mx-mr2+r*0.04, my-mr2+r*0.06), size=(mr2*2, mr2*2))
                Color(1, 1, 1, 0.28)
                hr = r * 0.26
                Ellipse(pos=(mx-hr*0.3, my+r*0.22), size=(hr*1.5, hr))
