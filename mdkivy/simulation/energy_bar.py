from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.uix.label import Label
from kivy.clock import Clock


class EnergyBar(Widget):
    """Vertical thermometer - fills and shifts colour based on system kinetic energy.

    Blue = cold / stable (Verlet).
    Red  = hot  / rising (Euler drift or energy injected).
    """

    def __init__(self, game_area_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.game_area = game_area_ref
        self._energy   = 0.0
        self._smooth   = 0.0   # exponential smoothing
        self._peak     = 600.0  # ceiling = avg speed in px/s (requires heavy injection to reach red)

        self.mode_label = Label(
            text='VERLET',
            size_hint=(None, None),
            font_size='11sp', bold=True,
            color=(0.3, 1.0, 0.5, 1),
            halign='center', valign='middle',
        )
        self.add_widget(self.mode_label)

        self.val_label = Label(
            text='0.0',
            size_hint=(None, None),
            font_size='10sp', bold=True,
            color=(0.7, 0.8, 1.0, 0.85),
            halign='center', valign='middle',
        )
        self.add_widget(self.val_label)

        Clock.schedule_interval(self._tick, 0.05)

    def feed(self, energy):
        self._energy = float(energy)
        alpha        = 0.25
        self._smooth = (1 - alpha) * self._smooth + alpha * self._energy

    def _colour_for_level(self, level):
        """Return (r, g, b) based on 0-1 fill level."""
        if level < 0.20:
            return (0.10, 0.40, 1.00)
        if level < 0.40:
            return (0.10, 0.85, 0.90)
        if level < 0.60:
            return (0.20, 0.95, 0.30)
        if level < 0.75:
            return (1.00, 0.85, 0.10)
        if level < 0.90:
            return (1.00, 0.45, 0.05)
        return (1.00, 0.10, 0.10)

    def _tick(self, dt):
        if self.height < 4:
            return
        # faster decay in Euler mode - no velocity feed there, so bar must fall on its own
        is_euler = self.game_area and not self.game_area.use_verlet
        self._smooth *= 0.97 if is_euler else 0.994
        self.canvas.clear()

        level = min(self._smooth / max(self._peak, 1.0), 1.0)
        r, g, b = self._colour_for_level(level)

        label_h = max(16, int(self.height * 0.08))
        pad     = 4
        bar_x   = self.x + pad
        bar_y   = self.y + label_h + pad
        bar_w   = self.width - pad * 2
        bar_h   = self.height - label_h * 2 - pad * 3
        fill_h  = max(0.0, bar_h * level)

        with self.canvas:
            # dark background
            Color(0.03, 0.05, 0.10, 1)
            Rectangle(pos=self.pos, size=self.size)

            # empty-bar track
            Color(0.10, 0.12, 0.18, 1)
            Rectangle(pos=(bar_x, bar_y), size=(bar_w, bar_h))

            # glow fill
            Color(r, g, b, 0.18)
            Rectangle(pos=(bar_x, bar_y), size=(bar_w, fill_h))

            # solid centre strip
            thin = max(4, int(bar_w * 0.35))
            cx   = bar_x + (bar_w - thin) / 2
            Color(r, g, b, 0.90)
            Rectangle(pos=(cx, bar_y), size=(thin, fill_h))

            # bright cap at top of fill
            if fill_h > 4:
                Color(1, 1, 1, 0.55)
                Rectangle(pos=(bar_x, bar_y + fill_h - 3), size=(bar_w, 3))

            # tick marks at 25 / 50 / 75 %
            Color(0.30, 0.35, 0.45, 0.50)
            for t in (0.25, 0.50, 0.75):
                ty = bar_y + bar_h * t
                Line(points=[bar_x, ty, bar_x + bar_w, ty], width=0.8)

            # outer border - colour matches fill
            Color(r * 0.55, g * 0.55, b * 0.55, 0.60)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.1)

        # mode label (top)
        mode = 'EULER' if (self.game_area and not self.game_area.use_verlet) else 'VERLET'
        fs = max(7, int(self.width * 0.45))
        self.mode_label.font_size  = f'{fs}sp'
        self.mode_label.color      = (r, g, b, 1)
        self.mode_label.text       = mode
        self.mode_label.texture_update()
        self.mode_label.size       = (self.width, label_h)
        self.mode_label.pos        = (self.x, self.top - label_h - 1)

        # value label (bottom) - shows per-molecule temperature
        self.val_label.font_size   = f'{fs}sp'
        self.val_label.text        = f'T={self._smooth:.1f}'
        self.val_label.texture_update()
        self.val_label.size        = (self.width, label_h)
        self.val_label.pos         = (self.x, self.y + 2)
