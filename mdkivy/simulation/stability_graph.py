import os
from collections import deque
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, RoundedRectangle, Ellipse
from kivy.clock import Clock
from mdkivy.paths import FONT_IMPACT

_FONT = FONT_IMPACT


class StabilityGraph(Widget):
    """Scrolling stability-score graph. Feed it via feed_score(0..1)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_points  = 120
        self.data_points = deque([1.0] * self.max_points, maxlen=self.max_points)
        self._draw_event = Clock.schedule_interval(self._draw, 1 / 30.0)

    def feed_score(self, score: float):
        self.data_points.append(max(0.0, min(1.0, score)))

    def stop(self):
        if self._draw_event:
            self._draw_event.cancel()
            self._draw_event = None

    @staticmethod
    def _colour(score):
        if score > 0.80:
            return (0.30, 0.92, 0.45)
        if score > 0.55:
            return (0.95, 0.88, 0.20)
        if score > 0.25:
            return (1.00, 0.65, 0.20)
        return (1.00, 0.32, 0.32)

    def _draw(self, dt):
        if self.height < 4 or self.opacity < 0.05:
            return
        self.canvas.clear()

        pad = max(8, int(self.width * 0.025))
        gx, gy = self.x + pad, self.y + pad
        gw, gh = self.width - pad * 2, self.height - pad * 2

        pts   = list(self.data_points)
        score = pts[-1] if pts else 1.0
        r, g, b = self._colour(score)
        n = self.max_points

        with self.canvas:
            Color(0.02, 0.04, 0.10, 0.97)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[(8, 8)] * 4)

            # grid lines
            Color(0.12, 0.20, 0.32, 0.55)
            for t in (0.25, 0.50, 0.75):
                ty = gy + gh * t
                Line(points=[gx, ty, gx + gw, ty], width=0.8)

            # stable-zone threshold line at 0.8
            Color(0.30, 0.92, 0.45, 0.30)
            Line(points=[gx, gy + gh * 0.8, gx + gw, gy + gh * 0.8], width=1.4)

            # graph line with glow
            if len(pts) >= 2:
                points = []
                for i, v in enumerate(pts):
                    px = gx + (i / (n - 1)) * gw
                    py = gy + v * gh
                    points.extend([px, py])
                Color(r, g, b, 0.10)
                Line(points=points, width=9.0)
                Color(r, g, b, 0.22)
                Line(points=points, width=5.0)
                Color(r, g, b, 1.00)
                Line(points=points, width=1.8)

            # live dot
            dot_x = gx + gw
            dot_y = gy + score * gh
            Color(1, 1, 1, 0.50)
            Ellipse(pos=(dot_x - 6, dot_y - 6), size=(12, 12))
            Color(r, g, b, 1.0)
            Ellipse(pos=(dot_x - 4, dot_y - 4), size=(8, 8))

            # border
            Color(r * 0.55, g * 0.55, b * 0.55, 0.70)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 8), width=1.4)
