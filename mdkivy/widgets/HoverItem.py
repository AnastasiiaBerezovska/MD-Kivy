from kivy.uix.image import Image
from kivymd.uix.behaviors import HoverBehavior
from kivy.core.window import Window

class HoverItem(Image, HoverBehavior):
    defaultSource = ""
    hoverSource = ""
    use = False
    
    def __init__(self, **kwargs):
        self.hoverSource = kwargs.pop("hoverSource")
        self.defaultSource = kwargs.pop("defaultSource")
        self.function = kwargs.pop("function")
        self.allow_stretch = True
        if "height" in kwargs:
            self.height = kwargs.pop("height")
        self.size_hint = kwargs.pop("size_hint")
        if "pos_hint" in kwargs:
            self.pos_hint = kwargs.pop("pos_hint")
        super().__init__(**kwargs)
        self.source = self.defaultSource
        self.detect_visible = False

    def on_enter(self, *args):
        self.use = True
        self.source = self.hoverSource

    def on_leave(self, *args):
        self.use = False
        self.source = self.defaultSource

    def on_touch_down(self, touch):
        if self.opacity < 0.1:
            return super().on_touch_down(touch)
        if self.collide_point(*touch.pos):
            self.use = True
            self.source = self.hoverSource
            self.function(0)
            # let hover fire again after a click
            self.hovering = False
            return True
        self.use = False
        return super().on_touch_down(touch)
