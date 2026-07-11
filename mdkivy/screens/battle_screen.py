"""
BattleScreen - two-player molecular temperature battle.

Left player  keys: Left-arrow  / Space / A  (Makey Makey floor pad 1)
Right player keys: Right-arrow / Enter / L  (Makey Makey floor pad 2)

Each keypress drops a fast molecule on the player's side.
First side to heat its arena to TEMP_TARGET (a temperature-like reading
that grows with total kinetic energy) wins; the match time is recorded.
The divider then shatters and the winner's molecules flood the loser's arena.
"""

import os, math, random, time
from kivy.uix.screenmanager import Screen
from mdkivy.inputs.dual_makey import DualMakeyInput
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import (Color, Ellipse, Rectangle, Line,
                            RoundedRectangle, Triangle)
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.animation import Animation
from mdkivy.paths import FONT_IMPACT

_FONT   = FONT_IMPACT

# -- tunable game constants -------------------------------------------------
TEMP_TARGET     = 373.15 # win when a side's temperature reading hits this (boiling point of water, K)
SPAWN_SPEED     = 300.0  # px/s - fast enough that no energy-kick is needed
GRAVITY         = 0.0
WALL_RESTITUTION= 1.0
MOL_R           = 13
MAX_MOLS_SIDE   = 40
PHYSICS_DT      = 1/30.0
DRAW_DT         = 1/30.0
HUD_DT          = 0.25
SPAWN_COOLDOWN  = 0.12   # min seconds between spawns per team
MAX_SPEED       = 550.0


class BattleScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._molecules       = []   # list of dicts {x,y,vx,vy,team}
        self._divider_alive   = True
        self._winner          = None
        self._state           = 'idle'  # idle | playing | flooding
        self._left_name       = 'Player 1'
        self._right_name      = 'Player 2'
        self._lb_ev           = None   # scheduled leaderboard transition
        self._phy_ev          = None
        self._drw_ev          = None
        self._hud_ev          = None
        self._divider_opacity = 1.0   # animated to 0 on break
        self._flash_opacity   = 0.0   # white flash when divider shatters
        self._shards          = []    # {x,y,vx,vy,size,life} divider debris
        self._pops            = []    # {x,y,r,max_r,life,max_life,cr,cg,cb,droplets} bubble pops

        self._last_spawn = {'left': 0.0, 'right': 0.0}
        self._root = FloatLayout()
        self.add_widget(self._root)

        self._build_backgrounds()
        self._build_target_panel()
        self._build_temp_labels()
        self._build_progress_bars()
        self._build_key_hints()
        self._build_win_label()
        self._build_back_button()
        self._build_arena()
        self._build_name_labels()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_backgrounds(self):
        with self._root.canvas.before:
            Color(0.01, 0.02, 0.06, 1)
            self._bg = Rectangle(pos=self._root.pos, size=self._root.size)
        self._root.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_):
        self._bg.pos  = self._root.pos
        self._bg.size = self._root.size

    def _build_target_panel(self):
        """Glowing goal indicator in the upper-centre."""
        self._target_panel = FloatLayout(
            size_hint=(0.18, 0.09),
            pos_hint={'center_x': 0.5, 'top': 0.99},
        )
        with self._target_panel.canvas.before:
            # outermost soft halo
            Color(1.0, 0.80, 0.10, 0.08)
            self._tgt_halo = RoundedRectangle(
                pos=self._target_panel.pos,
                size=self._target_panel.size,
                radius=[(18, 18)] * 4)
            # mid glow
            Color(1.0, 0.85, 0.15, 0.18)
            self._tgt_glow = RoundedRectangle(
                pos=self._target_panel.pos,
                size=self._target_panel.size,
                radius=[(14, 14)] * 4)
            # dark fill
            Color(0.06, 0.05, 0.01, 0.97)
            self._tgt_fill = RoundedRectangle(
                pos=self._target_panel.pos,
                size=self._target_panel.size,
                radius=[(12, 12)] * 4)
            # inner accent line (thinner, brighter)
            Color(1.0, 0.95, 0.30, 0.50)
            self._tgt_inner = Line(
                rounded_rectangle=(*self._target_panel.pos,
                                   *self._target_panel.size, 10),
                width=1.0)
            # outer border
            Color(1.0, 0.88, 0.20, 1.0)
            self._tgt_border = Line(
                rounded_rectangle=(*self._target_panel.pos,
                                   *self._target_panel.size, 12),
                width=2.2)

        def _sync_tgt(*_):
            p, s = self._target_panel.pos, self._target_panel.size
            g1 = 14; g2 = 7
            self._tgt_halo.pos  = (p[0]-g1, p[1]-g1)
            self._tgt_halo.size = (s[0]+g1*2, s[1]+g1*2)
            self._tgt_glow.pos  = (p[0]-g2, p[1]-g2)
            self._tgt_glow.size = (s[0]+g2*2, s[1]+g2*2)
            self._tgt_fill.pos  = p;  self._tgt_fill.size  = s
            self._tgt_inner.rounded_rectangle  = (*p, *s, 10)
            self._tgt_border.rounded_rectangle = (*p, *s, 12)
        self._target_panel.bind(pos=_sync_tgt, size=_sync_tgt)

        # "FIRST TO" subtitle
        self._target_sub = Label(
            text='— FIRST TO —',
            font_name=_FONT, font_size=16,
            halign='center', valign='middle',
            color=(1.0, 0.80, 0.20, 0.85),
            size_hint=(1, 0.45), pos_hint={'x': 0, 'top': 1},
        )
        self._target_sub.bind(size=self._target_sub.setter('text_size'))

        # big number
        self._target_lbl = Label(
            text=f'{TEMP_TARGET:g} K',
            font_name=_FONT, font_size=26,
            halign='center', valign='middle',
            color=(1.0, 0.96, 0.40, 1),
            bold=True,
            size_hint=(1, 0.55), pos_hint={'x': 0, 'y': 0},
        )
        self._target_lbl.bind(size=self._target_lbl.setter('text_size'))

        self._target_panel.add_widget(self._target_sub)
        self._target_panel.add_widget(self._target_lbl)
        self._root.add_widget(self._target_panel)

        # pulse the glow border
        import math as _m, time as _ti
        def _pulse_tgt(dt):
            t = _ti.time()
            a = 0.75 + 0.25 * _m.sin(t * 2.5)
            self._tgt_border.width = 1.8 + 0.8 * a
        self._tgt_pulse_ev = Clock.schedule_interval(_pulse_tgt, 1/30)

    def _build_temp_labels(self):
        """Temperature readout top-left and top-right."""
        self._left_temp = Label(
            text='LEFT TEMP\n0.0',
            font_name=_FONT, font_size=18,
            size_hint=(0.24, 0.09),
            pos_hint={'x': 0.01, 'top': 0.98},
            halign='center', valign='middle',
            color=(0.25, 0.80, 1.0, 1),
        )
        self._right_temp = Label(
            text='RIGHT TEMP\n0.0',
            font_name=_FONT, font_size=18,
            size_hint=(0.24, 0.09),
            pos_hint={'right': 0.99, 'top': 0.98},
            halign='center', valign='middle',
            color=(0.62, 0.38, 1.0, 1),
        )
        for lbl in (self._left_temp, self._right_temp):
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

    def _build_progress_bars(self):
        """Thin progress-to-target bars under each temp label."""
        self._left_bar = Label(
            text='',
            font_name=_FONT, font_size=11,
            size_hint=(0.26, 0.035),
            pos_hint={'x': 0.01, 'top': 0.88},
            halign='left', valign='middle',
            color=(0.25, 0.80, 1.0, 0.85),
        )
        self._right_bar = Label(
            text='',
            font_name=_FONT, font_size=11,
            size_hint=(0.26, 0.035),
            pos_hint={'right': 0.99, 'top': 0.88},
            halign='right', valign='middle',
            color=(0.62, 0.38, 1.0, 0.85),
        )
        for lbl in (self._left_bar, self._right_bar):
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

    def _build_key_hints(self):
        pass  # hints removed - players learn keys by testing

    def _build_win_label(self):
        self._win_lbl = Label(
            text='', font_name=_FONT, font_size=64,
            size_hint=(0.70, 0.16),
            pos_hint={'center_x': 0.5, 'center_y': 0.52},
            halign='center', valign='middle',
            color=(1, 1, 0.4, 0),
            outline_color=(0.7, 0.5, 0, 1),
            outline_width=4,
        )
        self._win_lbl.bind(size=self._win_lbl.setter('text_size'))
        self._root.add_widget(self._win_lbl)

    def _build_back_button(self):
        btn = Button(
            text='BACK', font_name=_FONT, font_size=16,
            size_hint=(0.07, 0.045),
            pos_hint={'x': 0.01, 'y': 0.955},
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
        btn.bind(pos=_sync, size=_sync, on_press=lambda *_: self._go_back())
        self._root.add_widget(btn)

    def _build_arena(self):
        """The main play area - a widget whose canvas we redraw each frame."""
        self._arena = FloatLayout(
            size_hint=(0.96, 0.72),
            pos_hint={'center_x': 0.5, 'top': 0.88},
        )
        self._root.add_widget(self._arena)

    def _build_name_labels(self):
        """Player name plates sit just below each half of the arena."""
        # arena: width=0.96 centered at 0.5 -> left half center~0.26, right~0.74
        # arena bottom = top(0.88) − height(0.72) = 0.16 -> labels sit below that
        self._left_name_lbl = Label(
            text=self._left_name,
            font_name=_FONT, font_size=24,
            size_hint=(0.44, 0.09),
            pos_hint={'center_x': 0.26, 'top': 0.155},
            halign='center', valign='middle',
            color=(0.25, 0.80, 1.0, 0.95),
            outline_color=(0.0, 0.25, 0.55, 1),
            outline_width=2,
        )
        self._right_name_lbl = Label(
            text=self._right_name,
            font_name=_FONT, font_size=24,
            size_hint=(0.44, 0.09),
            pos_hint={'center_x': 0.74, 'top': 0.155},
            halign='center', valign='middle',
            color=(0.62, 0.38, 1.0, 0.95),
            outline_color=(0.55, 0.15, 0.0, 1),
            outline_width=2,
        )
        for lbl in (self._left_name_lbl, self._right_name_lbl):
            lbl.bind(size=lbl.setter('text_size'))
            self._root.add_widget(lbl)

    # ==================================================================
    # Screen lifecycle
    # ==================================================================

    def on_enter(self, *args):
        # refresh name plates - names are injected by BattleNameScreen after construction
        self._left_name_lbl.text  = self._left_name
        self._right_name_lbl.text = self._right_name
        self._reset()
        # Guard: ignore touches for 0.5 s after entering so the tap that triggered
        # the BATTLE! button doesn't immediately spawn a molecule in the new screen.
        self._touch_ready = False
        Clock.schedule_once(lambda *_: setattr(self, '_touch_ready', True), 0.5)
        self._phy_ev = Clock.schedule_interval(self._physics, PHYSICS_DT)
        self._drw_ev = Clock.schedule_interval(self._draw,    DRAW_DT)
        self._hud_ev = Clock.schedule_interval(self._hud_tick, HUD_DT)
        # evdev-based per-device input (works even when both Makeys send the same key)
        self._dual_makey = DualMakeyInput(
            left_cb=lambda: self._remove_mol('right'),
            right_cb=lambda: self._remove_mol('left'),
        )
        # Unbind first to prevent double-binding if lifecycle fires unexpectedly
        Window.unbind(on_key_down=self._key_down)
        Window.bind(on_key_down=self._key_down)

    def on_pre_leave(self, *args):
        Window.unbind(on_key_down=self._key_down)
        if getattr(self, '_dual_makey', None):
            self._dual_makey.stop()
            self._dual_makey = None
        # cancel all scheduled events including the leaderboard transition
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
        self._state             = 'playing'
        self._match_start       = time.monotonic()
        self._match_time        = None
        self._last_spawn   = {'left': 0.0, 'right': 0.0}
        self._win_lbl.text = ''
        self._win_lbl.color     = (1, 1, 0.4, 0)

    # ==================================================================
    # Input
    # ==================================================================

    def _key_down(self, window, key, scancode, codepoint, modifiers):
        # evdev (DualMakeyInput) handles per-device routing when Makeys are connected.
        # Using the OS key event here would double-spawn because both Makeys send the
        # same key (Space), making every press also fire the wrong side via this handler.
        if getattr(self, '_dual_makey', None) and self._dual_makey._devices:
            return   # evdev is active - don't process OS key events at all
        if self._state != 'playing':
            return
        # fallback for when no Makey Makeys are connected (regular keyboard)
        if key in (276, 97, 32):
            self._remove_mol('right')
        elif key in (275, 108, 13, 271):
            self._remove_mol('left')

    def _spawn(self, team):
        a = self._arena
        if a.width < 10:
            return

        mid = a.x + a.width / 2
        r   = MOL_R

        side_mols = [m for m in self._molecules if m['team'] == team]
        if len(side_mols) >= MAX_MOLS_SIDE:
            return

        # spawn at the dead center of the arena, flung outward to the correct side
        x  = mid
        y  = a.y + a.height / 2  # this is the high at which spawns the mol, needs modification
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
        cr, cg, cb = (0.25, 0.80, 1.0) if team == 'left' else (0.62, 0.38, 1.0)
        life = 0.50
        self._pops.append({
            'x': m['x'], 'y': m['y'],
            'r': MOL_R * 0.3,
            'max_r': MOL_R * 4.0,
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
        r   = MOL_R
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
        # Vertical gate: only spawn if touch is inside the arena height.
        # Use arena widget if it is laid out; fall back to window proportions.
        a = self._arena
        if a.height > 10:
            in_arena_y = a.y <= py <= a.y + a.height
        else:
            in_arena_y = Window.height * 0.16 <= py <= Window.height * 0.88
        if not in_arena_y:
            return super().on_touch_down(touch)

        # Horizontal split: Window.width / 2 is always the visual centre line,
        # regardless of arena layout state or Screen coordinate transforms.
        win_mid = Window.width / 2
        dead    = Window.width * 0.05   # 5% each side - wide gap prevents near-divider misfires

        if px < win_mid - dead:
            team = 'left'
        elif px > win_mid + dead:
            team = 'right'
        else:
            return True   # centre dead zone

        now = Clock.get_time()
        if now - self._last_spawn[team] >= SPAWN_COOLDOWN:
            self._last_spawn[team] = now
            self._spawn_at(px, py, team)
        return True

    # ==================================================================
    # Physics
    # ==================================================================

    def _physics(self, dt):
        if self._state == 'idle':
            return
        a   = self._arena
        if a.width < 10:
            return
        ax, ay, aw, ah = a.x, a.y, a.width, a.height
        mid = ax + aw / 2
        r   = MOL_R
        mols = self._molecules

        for m in mols:
            m['vy'] -= GRAVITY * dt
            m['x']  += m['vx'] * dt
            m['y']  += m['vy'] * dt

            # floor / ceiling
            if m['y'] - r < ay:
                m['y'] = ay + r
                m['vy'] = abs(m['vy']) * WALL_RESTITUTION
            if m['y'] + r > ay + ah:
                m['y'] = ay + ah - r
                m['vy'] = -abs(m['vy']) * WALL_RESTITUTION

            # side walls
            if m['x'] - r < ax:
                m['x'] = ax + r
                m['vx'] = abs(m['vx']) * WALL_RESTITUTION
            if m['x'] + r > ax + aw:
                m['x'] = ax + aw - r
                m['vx'] = -abs(m['vx']) * WALL_RESTITUTION

            # divider
            if self._divider_alive:
                if m['team'] == 'left' and m['x'] + r > mid:
                    m['x'] = mid - r
                    m['vx'] = -abs(m['vx']) * 0.88
                elif m['team'] == 'right' and m['x'] - r < mid:
                    m['x'] = mid + r
                    m['vx'] = abs(m['vx']) * 0.88

        # hard-sphere collisions (optimised: skip if bounding-box miss)
        min_d = r * 2
        for i in range(len(mols)):
            for j in range(i + 1, len(mols)):
                m1, m2 = mols[i], mols[j]
                dx = m2['x'] - m1['x']
                dy = m2['y'] - m1['y']
                if abs(dx) > min_d or abs(dy) > min_d:
                    continue
                d2 = dx*dx + dy*dy
                if d2 < min_d * min_d and d2 > 0:
                    d   = d2 ** 0.5
                    nx  = dx / d;  ny = dy / d
                    ovr = (min_d - d) * 0.5
                    m1['x'] -= nx * ovr;  m1['y'] -= ny * ovr
                    m2['x'] += nx * ovr;  m2['y'] += ny * ovr
                    # elastic normal-component swap
                    v1n = m1['vx']*nx + m1['vy']*ny
                    v2n = m2['vx']*nx + m2['vy']*ny
                    m1['vx'] += (v2n - v1n) * nx
                    m1['vy'] += (v2n - v1n) * ny
                    m2['vx'] += (v1n - v2n) * nx
                    m2['vy'] += (v1n - v2n) * ny

        # speed cap - prevents energy from accumulating past MAX_SPEED after many kicks
        for m in mols:
            spd = (m['vx']**2 + m['vy']**2) ** 0.5
            if spd > MAX_SPEED:
                s = MAX_SPEED / spd
                m['vx'] *= s
                m['vy'] *= s

        # flash decay
        if self._flash_opacity > 0:
            self._flash_opacity = max(0.0, self._flash_opacity - 3.5 * dt)

        # shard particles
        for s in self._shards:
            s['x']    += s['vx'] * dt
            s['y']    += s['vy'] * dt
            s['vy']   -= GRAVITY * 3 * dt   # shards fall faster
            s['life'] -= dt
        self._shards = [s for s in self._shards if s['life'] > 0]

        # bubble pop animations
        for p in self._pops:
            frac    = 1.0 - p['life'] / p['max_life']
            p['r']  = p['max_r'] * frac           # ring expands outward
            for d in p['droplets']:
                d['dx'] += d['vx'] * dt
                d['dy'] += d['vy'] * dt
            p['life'] -= dt
        self._pops = [p for p in self._pops if p['life'] > 0]

    # -- HUD tick (runs at HUD_DT, not every physics frame) ------------

    def _hud_tick(self, *_):
        if self._state == 'playing':
            self._check_win()

    # -- temperature & win ----------------------------------------------

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

        # HUD - show temperature progress toward TEMP_TARGET
        pct_l = min(tl / TEMP_TARGET, 1.0)
        pct_r = min(tr / TEMP_TARGET, 1.0)
        b = 18
        self._left_temp.text  = f'{tl:.1f} / {TEMP_TARGET:g} K'
        self._right_temp.text = f'{tr:.1f} / {TEMP_TARGET:g} K'
        self._left_bar.text   = '█' * int(pct_l * b) + '░' * (b - int(pct_l * b))
        self._right_bar.text  = '█' * int(pct_r * b) + '░' * (b - int(pct_r * b))

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
        if winner == 'left':
            self._win_lbl.text = f'◀  {winner_name.upper()} WINS!'
            col = (0.25, 0.85, 1.0, 0)
        else:
            self._win_lbl.text = f'{winner_name.upper()} WINS!  ▶'
            col = (0.62, 0.38, 1.0, 0)

        self._win_lbl.color = col
        Animation(color=(*col[:3], 1), duration=0.55).start(self._win_lbl)

        # fast divider fade -> shatter -> flood -> leaderboard
        def _fade_div(dt):
            self._divider_opacity = max(0.0, self._divider_opacity - 0.18)
            if self._divider_opacity <= 0:
                self._divider_alive   = False
                self._flash_opacity   = 1.0   # white shockwave flash
                self._divider_opacity = 0.0
                self._start_flood()
                return False
        Clock.schedule_interval(_fade_div, 0.03)
        # go to leaderboard after flooding animation plays out
        self._lb_ev = Clock.schedule_once(self._go_to_leaderboard, 4.0)

    def _start_flood(self):
        self._state  = 'flooding'
        a            = self._arena
        mid          = a.x + a.width / 2
        ay, ah       = a.y, a.height
        toward_winner = -1 if self._winner == 'left' else 1

        # spawn shard debris along the divider line
        for _ in range(28):
            y     = random.uniform(ay, ay + ah)
            angle = random.uniform(0, math.pi * 2)
            spd   = random.uniform(120, 480)
            self._shards.append({
                'x': mid, 'y': y,
                'vx': spd * math.cos(angle),
                'vy': spd * math.sin(angle),
                'size': random.uniform(3, 9),
                'life': random.uniform(0.25, 0.75),
            })

        for m in self._molecules:
            if m['team'] == self._winner:
                # winner's HOT molecules surge into the loser's cold side
                m['vx'] = -toward_winner * random.uniform(500, 900)
                m['vy'] = random.uniform(-250, 250)
            else:
                # loser's cold molecules get pushed to their far wall
                m['vx'] = -toward_winner * random.uniform(150, 350)
                m['vy'] = random.uniform(-150, 150)

    # ==================================================================
    # Rendering
    # ==================================================================

    def _draw(self, dt):
        a = self._arena
        if a.width < 10:
            return

        ax, ay, aw, ah = a.x, a.y, a.width, a.height
        mid = ax + aw / 2
        r   = MOL_R

        c = a.canvas
        c.clear()
        with c:
            # -- arena backgrounds -------------------------------------
            Color(0.04, 0.07, 0.18, 0.92)
            Rectangle(pos=(ax, ay), size=(aw, ah))

            # -- arena outer border ------------------------------------
            Color(0.25, 0.45, 0.75, 0.45)
            Line(rectangle=(ax, ay, aw, ah), width=1.6)

            # -- divider -----------------------------------------------
            if self._divider_opacity > 0.01:
                op = self._divider_opacity
                Color(0.45, 0.92, 1.0, 0.06 * op)
                Line(points=[mid, ay, mid, ay + ah], width=22)
                Color(0.45, 0.92, 1.0, 0.14 * op)
                Line(points=[mid, ay, mid, ay + ah], width=12)
                Color(0.45, 0.92, 1.0, 0.60 * op)
                Line(points=[mid, ay, mid, ay + ah], width=2.8)
                # notch marks
                Color(0.55, 0.95, 1.0, 0.30 * op)
                step = max(16, int(ah) // 20)
                for ty in range(int(ay + step // 2), int(ay + ah), step):
                    Line(points=[mid - 5, ty, mid + 5, ty], width=1.0)

            # -- shockwave flash ---------------------------------------
            if self._flash_opacity > 0.01:
                fo = self._flash_opacity
                # wide white pulse centred on the divider
                Color(1.0, 1.0, 1.0, fo * 0.55)
                Rectangle(pos=(mid - 60, ay), size=(120, ah))
                Color(1.0, 0.95, 0.7, fo * 0.30)
                Rectangle(pos=(mid - 140, ay), size=(280, ah))

            # -- divider debris shards ---------------------------------
            for s in self._shards:
                alpha = max(0.0, s['life'] * 1.8)
                Color(0.55, 0.95, 1.0, min(alpha, 0.9))
                sz = s['size']
                Rectangle(pos=(s['x'] - sz/2, s['y'] - sz/2), size=(sz, sz))

            # -- bubble pop effects ------------------------------------
            for p in self._pops:
                frac  = 1.0 - p['life'] / p['max_life']   # 0->1 as pop ages
                alpha = max(0.0, 1.0 - frac)
                cr2, cg2, cb2 = p['cr'], p['cg'], p['cb']
                # outer expanding ring
                if p['r'] > 1:
                    Color(cr2, cg2, cb2, alpha * 0.90)
                    Line(circle=(p['x'], p['y'], p['r']), width=2.8)
                # inner ring (thinner, white-ish)
                ir = p['r'] * 0.55
                if ir > 1:
                    Color(1.0, 1.0, 1.0, alpha * 0.55)
                    Line(circle=(p['x'], p['y'], ir), width=1.4)
                # tiny droplets spraying outward
                dr = max(1.5, MOL_R * 0.28 * alpha)
                for d in p['droplets']:
                    Color(cr2, cg2, cb2, alpha * 0.80)
                    Ellipse(pos=(p['x']+d['dx']-dr, p['y']+d['dy']-dr),
                            size=(dr*2, dr*2))

            # -- molecules ---------------------------------------------
            for m in self._molecules:
                mx, my = m['x'], m['y']
                spd  = self._speed(m)
                heat = min(spd / SPAWN_SPEED, 1.0)

                if m['team'] == 'left':
                    cr, cg, cb = 0.10 + 0.90*heat, 0.55 + 0.45*heat, 1.0
                else:
                    cr, cg, cb = 0.62 + 0.38*heat, 0.30 + 0.70*heat, 1.0

                # glow
                gr = r * 1.55
                Color(cr, cg, cb, 0.12)
                Ellipse(pos=(mx-gr, my-gr), size=(gr*2, gr*2))
                # dark base
                Color(cr*0.14, cg*0.14, cb*0.14, 1)
                Ellipse(pos=(mx-r, my-r), size=(r*2, r*2))
                # lit sphere
                Color(cr, cg, cb, 1)
                mr2 = r * 0.82
                Ellipse(pos=(mx-mr2+r*0.04, my-mr2+r*0.06), size=(mr2*2, mr2*2))
                # specular highlight
                Color(1, 1, 1, 0.40)
                hr = r * 0.26
                Ellipse(pos=(mx-hr*0.3, my+r*0.22), size=(hr*1.5, hr))

            # -- target progress overlay lines (team colours) ----------
            bar_h = max(4, ah * 0.012)
            pct_l = min(self._side_thermal('left') / TEMP_TARGET, 1.0)
            Color(0.25, 0.80, 1.0, 0.35)
            Rectangle(pos=(ax, ay), size=(aw/2, bar_h))
            Color(0.25, 0.80, 1.0, 0.85)
            Rectangle(pos=(ax, ay), size=(aw/2 * pct_l, bar_h))
            pct_r = min(self._side_thermal('right') / TEMP_TARGET, 1.0)
            Color(0.62, 0.38, 1.0, 0.35)
            Rectangle(pos=(mid, ay), size=(aw/2, bar_h))
            Color(0.62, 0.38, 1.0, 0.85)
            Rectangle(pos=(mid, ay), size=(aw/2 * pct_r, bar_h))
