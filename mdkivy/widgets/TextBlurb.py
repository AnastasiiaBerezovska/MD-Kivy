from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import BooleanProperty, StringProperty, NumericProperty, ListProperty
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.animation import Animation
import os

from mdkivy.paths import GRAPHICS_DIR


class TextBlurb(Widget):
    """Toggleable info popup - dark navy card with cyan border, bold white text, close button."""
    is_visible = BooleanProperty(False)
    text       = StringProperty("This is a text blurb.")
    font_size  = NumericProperty(11)
    padding    = ListProperty([14, 10, 14, 10])

    def __init__(self, **kwargs):
        self.parent_size_prop = kwargs.pop("parent_size_prop")
        self.parent_pos_prop  = kwargs.pop("parent_pos_prop")
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (400, 200)
        self.opacity = 0   # whole widget starts invisible; animated in

        with self.canvas.before:
            self.bg_color = Color(0.04, 0.07, 0.15, 1.0)
            self.bg_rect  = RoundedRectangle(pos=self.pos, size=self.size, radius=[(10, 10)] * 4)
            self.bdr_color = Color(0.0, 0.60, 0.95, 0.90)
            self.bdr_rect  = Line(
                rounded_rectangle=[self.x, self.y, self.width, self.height, 10],
                width=1.6,
            )

        self.bind(pos=self._update_background, size=self._update_background)

        self.text_label = Label(
            text=self.text,
            font_size=self.font_size * self.width // 400,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            text_size=(self.width - self.padding[0] - self.padding[2], None),
        )
        self.text_label.bind(size=self._update_text_size)
        self.add_widget(self.text_label)

        # PNG close button - top-right corner
        _close_normal = os.path.join(GRAPHICS_DIR, "Close.png")
        _close_hover  = os.path.join(GRAPHICS_DIR, "Close_Highlighted.png")
        self._close_btn = Button(
            size_hint=(None, None),
            size=(28, 28),
            background_normal=_close_normal,
            background_down=_close_hover,
            background_color=(1, 1, 1, 1),
            border=(0, 0, 0, 0),
        )
        self._close_btn.bind(on_press=lambda *a: self.hide())
        self.add_widget(self._close_btn)

        self._update_text_layout()
        self.bind(parent=self._bind_parent_events)

    def on_touch_down(self, touch):
        # A hidden popup must not intercept taps: several popups overlap at the
        # same spot, and an invisible one on top would otherwise swallow the
        # close-button tap meant for the visible one (and block spawning).
        if not self.is_visible:
            return False
        # Visible: let the close button handle its tap, and swallow taps on the
        # card body so nothing spawns in the game area behind it.
        if super().on_touch_down(touch):
            return True
        return self.collide_point(*touch.pos)

    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        Animation.cancel_all(self)
        if self.is_visible:
            Animation(opacity=1, duration=0.18, t='out_quad').start(self)
        else:
            Animation(opacity=0, duration=0.14, t='in_quad').start(self)

    def show(self):
        if not self.is_visible:
            self.toggle_visibility()

    def hide(self):
        if self.is_visible:
            self.toggle_visibility()

    def _update_background(self, *args):
        self.bg_rect.pos  = self.pos
        self.bg_rect.size = self.size
        self.bdr_rect.rounded_rectangle = [self.x, self.y, self.width, self.height, 10]
        self._update_text_layout()

    def _update_text_size(self, instance, value):
        self.text_label.text_size = (self.width - self.padding[0] - self.padding[2], None)
        self.text_label.size      = self.text_label.texture_size

    def _update_text_layout(self, *args):
        inner_w = max(1, self.width - self.padding[0] - self.padding[2])
        self.text_label.font_size  = self.font_size * self.width // 400
        self.text_label.text_size  = (inner_w, None)
        self.text_label.texture_update()
        self.text_label.size = self.text_label.texture_size
        self.text_label.pos  = (self.x + self.padding[0], self.y + self.padding[3])
        self._close_btn.pos  = (self.right - self._close_btn.width - 4,
                                self.top   - self._close_btn.height - 4)

    def _bind_parent_events(self, instance, parent):
        if parent:
            parent.bind(size=self._resize_with_parent, pos=self._resize_with_parent)
            self._resize_with_parent()

    def _resize_with_parent(self, *args):
        if self.parent:
            w       = self.parent.width * self.parent_size_prop[0]
            inner_w = w - self.padding[0] - self.padding[2]

            self.text_label.font_size  = self.font_size * w // 400
            self.text_label.text_size  = (inner_w, None)
            self.text_label.texture_update()
            text_h = self.text_label.texture_size[1]

            h = text_h + self.padding[1] + self.padding[3] + self._close_btn.height + 4

            self.size = (w, h)
            self.pos  = (
                self.parent.width  * (self.parent_pos_prop[0] - self.parent_size_prop[0] * 0.5),
                self.parent.height *  self.parent_pos_prop[1] - h * 0.5,
            )
            self.bg_rect.pos  = self.pos
            self.bg_rect.size = self.size
            self.bdr_rect.rounded_rectangle = [self.x, self.y, self.width, self.height, 10]
            self.text_label.size = self.text_label.texture_size
            self.text_label.pos  = (self.x + self.padding[0], self.y + self.padding[3])
            self._close_btn.pos  = (self.right - self._close_btn.width - 4,
                                    self.top   - self._close_btn.height - 4)
