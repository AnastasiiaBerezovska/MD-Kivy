from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle, Ellipse
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.properties import ListProperty


class ArduinoGraph(Widget):
    background_color = ListProperty([0.03, 0.06, 0.12, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.size_hint = (0.6, 0.25)
        self.pos_hint  = {'right': 0.98}

        self.max_points  = 300
        self.data_points = [0] * self.max_points

        self.motion_label = Label(
            text='Shake: Low (0%)',
            size_hint=(None, None),
            bold=True,
            color=(0.6, 1.0, 0.6, 1),
            font_size='12sp',
        )
        self.add_widget(self.motion_label)

        self.bind(size=self._place_label, pos=self._place_label)
        Clock.schedule_interval(self.update_graph, 0.02)

    # -- helpers --------------------------------------------------------------

    def _colour(self, intensity):
        if intensity < 0.05:
            return (0.30, 1.00, 0.30)
        if intensity < 0.15:
            return (0.60, 1.00, 0.30)
        if intensity < 0.35:
            return (1.00, 1.00, 0.30)
        if intensity < 0.60:
            return (1.00, 0.50, 0.20)
        return (1.00, 0.20, 0.20)

    def _place_label(self, *args):
        fs = max(10, int(self.height * 0.13))
        self.motion_label.font_size = f'{fs}sp'
        self.motion_label.texture_update()
        self.motion_label.size = self.motion_label.texture_size
        self.motion_label.pos  = (
            self.x + max(8, int(self.width * 0.03)),
            self.top - self.motion_label.height - max(4, int(self.height * 0.06)),
        )

    # -- data -----------------------------------------------------------------

    def add_data_point(self, value):
        if self.data_points:
            value = 0.45 * self.data_points[-1] + 0.55 * value
        self.data_points.pop(0)
        self.data_points.append(value)

    def feed_arduino(self, x, y, z, shake_intensity=0):
        normalized = min(shake_intensity / 100.0, 1.0)
        self.add_data_point(normalized)

        if shake_intensity < 10:
            level = 'Low'
        elif shake_intensity < 30:
            level = 'Medium'
        else:
            level = 'Strong'

        r, g, b = self._colour(normalized)
        self.motion_label.text  = f'Shake: {level}  ({shake_intensity:.0f}%)'
        self.motion_label.color = (r, g, b, 1)

    # -- drawing ---------------------------------------------------------------

    def update_graph(self, dt):
        if self.height < 4:
            return
        self.canvas.clear()

        pad       = max(6, int(self.width * 0.015))
        gx        = self.x + pad
        gy        = self.y + pad
        gw        = self.width  - pad * 2
        gh        = self.height - pad * 2
        intensity = self.data_points[-1]
        r, g, b   = self._colour(intensity)

        with self.canvas:
            # -- background ------------------------------------------------
            Color(0.03, 0.06, 0.12, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[(8, 8)] * 4)

            # -- grid lines at 25 / 50 / 75 % ----------------------------
            Color(0.12, 0.20, 0.32, 0.65)
            for t in (0.25, 0.50, 0.75):
                ty = gy + gh * t
                Line(points=[gx, ty, gx + gw, ty], width=0.8)

            # -- graph line with glow layers -------------------------------
            points = []
            for i in range(1, len(self.data_points)):
                px = gx + (i / self.max_points) * gw
                py = gy + self.data_points[i] * gh
                points.extend([px, py])

            if len(points) >= 4:
                Color(r, g, b, 0.10)
                Line(points=points, width=9.0)   # outer glow
                Color(r, g, b, 0.20)
                Line(points=points, width=5.0)   # mid glow
                Color(r, g, b, 1.00)
                Line(points=points, width=1.8)   # crisp core

            # -- live dot at the right edge --------------------------------
            if intensity > 0.02:
                dot_x = gx + gw
                dot_y = gy + intensity * gh
                Color(1, 1, 1, 0.55)
                Ellipse(pos=(dot_x - 6, dot_y - 6), size=(12, 12))
                Color(r, g, b, 1.0)
                Ellipse(pos=(dot_x - 4, dot_y - 4), size=(8, 8))

            # -- coloured border -------------------------------------------
            Color(r * 0.55, g * 0.55, b * 0.55, 0.70)
            Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, 8),
                width=1.4,
            )

        self._place_label()
