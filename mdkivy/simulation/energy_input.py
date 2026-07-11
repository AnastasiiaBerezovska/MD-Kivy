from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.uix.label import Label
from kivy.clock import Clock


class EnergyInputWidget(Widget):
    """Touch-and-drag panel to inject kinetic energy into molecules.

    Drag distance -> energy boost -> molecules speed up -> temperature rises.
    Pulsing orange/red circle shows how much energy was just added.
    """

    def __init__(self, game_area_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.game_area  = game_area_ref
        self._touch_pos = None
        self._pulse     = 0.0   # 0-1, decays after injection

        self.hint = Label(
            text='[b]TOUCH & DRAG\nto inject energy[/b]',
            markup=True,
            halign='center', valign='middle',
            size_hint=(None, None),
            color=(0.50, 0.78, 1.00, 0.80),
            font_size='11sp',
        )
        self.add_widget(self.hint)
        self.bind(pos=self._place_hint, size=self._place_hint)
        Clock.schedule_interval(self._tick, 0.05)

    # -- hint label placement --------------------------------------------------

    def _place_hint(self, *args):
        self.hint.text_size   = (self.width * 0.85, None)
        self.hint.font_size   = f'{max(8, int(self.height * 0.11))}sp'
        self.hint.texture_update()
        self.hint.size        = self.hint.texture_size
        self.hint.pos         = (
            self.center_x - self.hint.width  / 2,
            self.center_y - self.hint.height / 2,
        )

    # -- touch handling --------------------------------------------------------

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_pos = touch.pos
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._touch_pos:
            dx     = touch.pos[0] - self._touch_pos[0]
            dy     = touch.pos[1] - self._touch_pos[1]
            drag   = (dx ** 2 + dy ** 2) ** 0.5
            ref    = max(min(self.width, self.height) * 0.30, 1.0)
            amount = min(drag / ref, 1.0)
            self._pulse     = max(self._pulse, amount)
            if self.game_area and amount > 0.01:
                self.game_area.inject_energy(amount)
            self._touch_pos = touch.pos
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._touch_pos:
            self._touch_pos = None
            return True
        return super().on_touch_up(touch)

    # -- drawing ---------------------------------------------------------------

    def _tick(self, dt):
        if self.height < 4:
            return
        self._pulse *= 0.80
        self.canvas.clear()

        e   = self._pulse
        r   = min(1.0, 0.15 + e * 1.70)
        g   = max(0.0, 0.72 - e * 0.90)
        b   = max(0.0, 0.85 - e * 1.20)

        with self.canvas:
            Color(0.03, 0.06, 0.12, 1)
            Rectangle(pos=self.pos, size=self.size)

            if e > 0.03:
                cx  = self.center_x
                cy  = self.center_y
                rad = e * min(self.width, self.height) * 0.44
                Color(r, g, b, 0.18)
                Ellipse(pos=(cx - rad, cy - rad), size=(rad * 2, rad * 2))
                Color(r, g, b, 0.70)
                r2  = rad * 0.38
                Ellipse(pos=(cx - r2, cy - r2), size=(r2 * 2, r2 * 2))

            # border - brightens when injecting
            border_a = 0.35 + e * 0.50
            Color(r * 0.70, g * 0.70, b * 0.70, border_a)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)

        # hide hint while actively injecting
        self.hint.opacity = max(0.0, 1.0 - e * 7)
        self._place_hint()
