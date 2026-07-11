from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.core.window import Window
import math

_UI_H = min(Window.height, 1000)

class Speedometer(Widget):
    def __init__(self, performance_monitor, **kwargs):
        super().__init__(**kwargs)
        self.monitor = performance_monitor
        self.size_hint = self.size_hint or (None, None)
        if self.size_hint == (None, None):
            self.size = (200, 200)
        self.pos_hint = getattr(self, 'pos_hint', {'right': 0.99, 'top': 0.94})
        self.current_angle = 135

        self.percent_label = Label(
            text="0%",
            font_size=_UI_H * 0.025,
            color=(1, 1, 1, 1),
            bold=True,
            size_hint=(None, None),
            size=(100, 30)
        )
        self.add_widget(self.percent_label)
        Clock.schedule_interval(self.update_speedometer, 0.02)

    # red -> orange -> yellow -> lime -> green
    _TICK_COLORS = [
        (0.04, 0.82, 0.36),
        (0.08, 0.85, 0.30),
        (0.12, 0.88, 0.24),
        (0.18, 0.92, 0.18),
        (0.38, 0.97, 0.10),
        (0.62, 0.97, 0.08),
        (0.88, 0.92, 0.08),
        (1.00, 0.74, 0.05),
        (1.00, 0.52, 0.05),
        (1.00, 0.32, 0.05),
        (1.00, 0.15, 0.08),
    ]

    def update_speedometer(self, dt):
        self.canvas.clear()
        cpu_percent = min(self.monitor._target_usage, 100)
        target_angle = 135 + (cpu_percent * 270 / 100)
        self.current_angle += (target_angle - self.current_angle) * 0.1

        side   = min(self.width, self.height)
        radius = side / 2.0
        cx     = self.x + self.width  / 2.0
        cy     = self.y + self.height / 2.0
        sq_x   = cx - radius
        sq_y   = cy - radius

        tick_outer  = radius * 0.90
        tick_inner  = radius * 0.70
        needle_len  = radius * 0.76

        with self.canvas:
            # -- outer glow rings ------------------------------------------
            for expand, alpha in ((0.16, 0.06), (0.10, 0.10), (0.05, 0.16)):
                g = radius * expand
                Color(0.20, 0.55, 1.0, alpha)
                Ellipse(pos=(sq_x - g, sq_y - g), size=(side + g*2, side + g*2))

            # -- main ring -------------------------------------------------
            Color(0.14, 0.32, 0.72, 1)
            Ellipse(pos=(sq_x, sq_y), size=(side, side))

            # -- bright inner rim (thin highlight) -------------------------
            Color(0.40, 0.65, 1.0, 0.55)
            Line(circle=(cx, cy, radius * 0.93), width=1.2)

            # -- dark interior ---------------------------------------------
            brd = radius * 0.085
            Color(0.02, 0.03, 0.09, 1)
            Ellipse(pos=(sq_x + brd, sq_y + brd),
                    size=(side - brd*2, side - brd*2))

            # -- coloured ticks --------------------------------------------
            for i, (tr, tg, tb) in enumerate(self._TICK_COLORS):
                angle = 135 + i * 27
                rad   = math.radians(angle)
                cos_a, sin_a = math.cos(rad), math.sin(rad)
                x1 = cx + tick_inner * cos_a
                y1 = cy + tick_inner * sin_a
                x2 = cx + tick_outer * cos_a
                y2 = cy + tick_outer * sin_a
                # outer glow
                Color(tr, tg, tb, 0.22)
                Line(points=[x1, y1, x2, y2], width=5)
                # mid glow
                Color(tr, tg, tb, 0.55)
                Line(points=[x1, y1, x2, y2], width=2.8)
                # crisp core
                Color(tr, tg, tb, 1.0)
                Line(points=[x1, y1, x2, y2], width=1.5)

            # -- needle ----------------------------------------------------
            rad = math.radians(self.current_angle)
            nx  = cx + needle_len * math.cos(rad)
            ny  = cy + needle_len * math.sin(rad)
            # wide soft glow
            Color(1, 1, 1, 0.12)
            Line(points=[cx, cy, nx, ny], width=14)
            # mid glow
            Color(1, 1, 1, 0.35)
            Line(points=[cx, cy, nx, ny], width=5)
            # sharp needle
            Color(1, 1, 1, 1)
            Line(points=[cx, cy, nx, ny], width=1.8)

            # -- centre cap ------------------------------------------------
            dot_r = radius * 0.075
            Color(0.15, 0.40, 0.90, 1)
            Ellipse(pos=(cx - dot_r, cy - dot_r), size=(dot_r*2, dot_r*2))
            Color(0.70, 0.85, 1.0, 0.90)
            Ellipse(pos=(cx - dot_r*0.45, cy - dot_r*0.45),
                    size=(dot_r*0.9, dot_r*0.9))

        # percent label - slightly below centre so the needle doesn't overlap it
        self.percent_label.text      = f"{int(cpu_percent)}%"
        self.percent_label.font_size = int(side * 0.15)
        self.percent_label.bold      = True
        lw = self.percent_label.texture_size[0] if self.percent_label.texture else side * 0.15
        lh = self.percent_label.texture_size[1] if self.percent_label.texture else side * 0.15
        self.percent_label.pos = (cx - lw / 2, cy - lh / 2 - radius * 0.18)
