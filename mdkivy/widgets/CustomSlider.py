from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse


class CustomSlider(Widget):
    value = NumericProperty(0)
    min   = NumericProperty(0)
    max   = NumericProperty(100)
    step  = NumericProperty(1)
    slider_length = NumericProperty(200)
    is_active     = BooleanProperty(False)
    track_image   = StringProperty("")
    thumb_image   = StringProperty("")

    _TRACK_H   = 6      # track bar height
    _THUMB_D   = 28     # thumb diameter
    _FILL_CLR  = (0.15, 0.55, 1.0,  1.0)   # blue fill left of thumb
    _TRACK_CLR = (0.18, 0.22, 0.32, 1.0)   # dark gray unfilled track
    _THUMB_CLR = (0.20, 0.60, 1.0,  1.0)   # thumb colour
    _GLOW_CLR  = (0.25, 0.65, 1.0,  0.25)  # soft glow ring around thumb

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, None)

        with self.canvas:
            # unfilled track (full width, drawn first)
            Color(*self._TRACK_CLR)
            self._track_bg = RoundedRectangle(pos=(0, 0), size=(1, self._TRACK_H),
                                              radius=[(self._TRACK_H // 2,) * 2] * 4)
            # filled track (left of thumb)
            Color(*self._FILL_CLR)
            self._track_fill = RoundedRectangle(pos=(0, 0), size=(1, self._TRACK_H),
                                                radius=[(self._TRACK_H // 2,) * 2] * 4)
            # glow ring behind thumb
            Color(*self._GLOW_CLR)
            self._glow = Ellipse(pos=(0, 0), size=(self._THUMB_D + 14,) * 2)
            # thumb
            Color(*self._THUMB_CLR)
            self._thumb = Ellipse(pos=(0, 0), size=(self._THUMB_D,) * 2)

        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    # -- touch handling ------------------------------------------------------

    def on_touch_down(self, touch):
        # only left mouse button; skip scroll/hover
        if getattr(touch, 'button', 'left') not in ('left', None):
            return False
        if self.collide_point(*touch.pos):
            # refuse to activate if any widget already owns this touch
            if touch.grab_list:
                return False
            self.is_active = True
            touch.grab(self)
            self._move(touch.x)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self._move(touch.x)
            return True
        return False  # never let a non-grabbed move fall through to other sliders

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            self.is_active = False
            touch.ungrab(self)
            return True
        return False

    # -- value / position helpers ---------------------------------------------

    def _move(self, touch_x):
        x_min = self.x
        x_max = x_min + self.slider_length - self._THUMB_D
        raw = self.min + (self.max - self.min) * ((min(max(touch_x, x_min), x_max) - x_min)
                                                    / max(self.slider_length - self._THUMB_D, 1))
        self.value = max(self.min, min(round((raw - self.min) / self.step) * self.step + self.min,
                                       self.max))

    def _thumb_x(self):
        """Absolute x of the left edge of the thumb."""
        return self.x + (self.value - self.min) / max(self.max - self.min, 1e-9) * (
            self.slider_length - self._THUMB_D)

    def _redraw(self, *_):
        self.slider_length = self.width
        cy = self.center_y

        tx = self._thumb_x()
        th = self._TRACK_H
        td = self._THUMB_D
        gd = td + 14

        # full track
        self._track_bg.pos  = (self.x, cy - th / 2)
        self._track_bg.size = (self.slider_length, th)

        # filled portion (left of thumb centre)
        fill_w = max(tx - self.x + td / 2, th)
        self._track_fill.pos  = (self.x, cy - th / 2)
        self._track_fill.size = (fill_w, th)

        # glow
        self._glow.pos  = (tx + td / 2 - gd / 2, cy - gd / 2)
        self._glow.size = (gd, gd)

        # thumb
        self._thumb.pos  = (tx, cy - td / 2)
        self._thumb.size = (td, td)
