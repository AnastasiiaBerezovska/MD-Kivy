from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from mdkivy.widgets.HoverItem import HoverItem


class SpinnerBox(FloatLayout):
    """
    Collapsed: arrows sit close together with PRESETS image between them  ◄ PRESETS ►
    Click anywhere -> arrows slide to edges, preset name fades in  ◄ SOLID ►
    Tap the preset name image to collapse again.
    on_expand(bool) callback notifies caller so CREATE can appear/disappear.
    """

    def __init__(self, defaultValue, possibleValues, on_expand=None, **kwargs):
        super().__init__(**kwargs)
        self.possibleValues = possibleValues
        self.value = defaultValue
        self.expanded = False
        self._on_expand_cb = on_expand
        self._animating = False

        # Center image: PRESETS when collapsed, preset name when expanded
        self.presets_img = Image(
            source="Graphics/Presets.png",
            size_hint=(0.55, 0.85),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.spinner = HoverItem(
            size_hint=(0.55, 0.85),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            hoverSource=f"Graphics/{possibleValues[defaultValue]}.png",
            defaultSource=f"Graphics/{possibleValues[defaultValue]}.png",
            function=lambda x: self.toggle_expand(),  # tap preset name to collapse
            opacity=0,
        )

        # Arrows use absolute positioning so we can animate their x
        self.left_arrow = HoverItem(
            size_hint=(None, None),
            hoverSource="Graphics/Left-Arrow_Highlighted.png",
            defaultSource="Graphics/Left-Arrow.png",
            function=lambda x: self._on_arrow(-1),
        )
        self.right_arrow = HoverItem(
            size_hint=(None, None),
            hoverSource="Graphics/Right-Arrow_Highlighted.png",
            defaultSource="Graphics/Right-Arrow.png",
            function=lambda x: self._on_arrow(1),
        )

        self.add_widget(self.presets_img)
        self.add_widget(self.spinner)
        self.add_widget(self.left_arrow)
        self.add_widget(self.right_arrow)

        self.bind(pos=self._place_arrows, size=self._place_arrows)

    # --- helpers ---

    def _aw(self):
        return max(20, self.width * 0.16)

    def _ah(self):
        return max(20, self.height * 0.80)

    def _arrow_y(self):
        return self.y + (self.height - self._ah()) / 2

    def _collapsed_positions(self):
        aw = self._aw()
        cx = self.x + self.width / 2
        gap = aw * 0.45
        return cx - aw - gap, cx + gap

    def _expanded_positions(self):
        aw = self._aw()
        margin = self.width * 0.02
        return self.x + margin, self.x + self.width - aw - margin

    # --- layout ---

    def _place_arrows(self, *args):
        """Snap arrows to the correct position (no animation) - used on resize."""
        if self._animating:
            return
        aw, ah = self._aw(), self._ah()
        ay = self._arrow_y()
        self.left_arrow.size = (aw, ah)
        self.right_arrow.size = (aw, ah)
        self.left_arrow.y = ay
        self.right_arrow.y = ay
        lx, rx = self._expanded_positions() if self.expanded else self._collapsed_positions()
        self.left_arrow.x = lx
        self.right_arrow.x = rx

    # --- touch ---

    def on_touch_down(self, touch):
        """Any tap when collapsed -> expand."""
        if self.collide_point(*touch.pos) and not self.expanded:
            self.toggle_expand()
            return True
        return super().on_touch_down(touch)

    # --- expand / collapse ---

    def toggle_expand(self):
        from kivy.animation import Animation
        self._animating = True

        aw, ah = self._aw(), self._ah()
        ay = self._arrow_y()
        self.left_arrow.size = (aw, ah)
        self.right_arrow.size = (aw, ah)
        self.left_arrow.y = ay
        self.right_arrow.y = ay

        if self.expanded:
            lx, rx = self._collapsed_positions()
            Animation(opacity=0, duration=0.12).start(self.spinner)
            Animation(opacity=1, duration=0.20).start(self.presets_img)
            self.expanded = False
        else:
            lx, rx = self._expanded_positions()
            Animation(opacity=1, duration=0.20).start(self.spinner)
            Animation(opacity=0, duration=0.12).start(self.presets_img)
            self.expanded = True

        def _done(*_a):
            self._animating = False

        anim_l = Animation(x=lx, duration=0.22)
        anim_r = Animation(x=rx, duration=0.22)
        anim_l.bind(on_complete=_done)
        anim_l.start(self.left_arrow)
        anim_r.start(self.right_arrow)

        if self._on_expand_cb:
            self._on_expand_cb(self.expanded)

    # --- arrow interaction ---

    def _on_arrow(self, delta):
        if self.expanded:
            self.updateState(delta)

    def updateState(self, delta):
        self.value = (self.value + delta) % len(self.possibleValues)
        preset = self.possibleValues[self.value]
        self.spinner.source = f"Graphics/{preset}.png"
        self.spinner.hoverSource = f"Graphics/{preset}.png"
        self.spinner.defaultSource = f"Graphics/{preset}.png"
