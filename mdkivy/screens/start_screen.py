from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.uix.label import Label
from mdkivy.widgets.HoverItem import HoverItem
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.properties import NumericProperty
import os
import gc
from mdkivy.paths import FONT_IMPACT

class _TutorialOverlay(FloatLayout):
    """Passes all touches through when invisible so buttons behind it stay clickable."""
    def on_touch_down(self, touch):
        if self.opacity < 0.1:
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.opacity < 0.1:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.opacity < 0.1:
            return False
        return super().on_touch_up(touch)


class FadeOverlay(Widget):
    opacity_level = NumericProperty(1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(0, 0, 0, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect, opacity_level=self.update_opacity)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def update_opacity(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0, 0, 0, self.opacity_level)
            self.rect = Rectangle(pos=self.pos, size=self.size)

class StartScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "StartScreen"

        self.root = FloatLayout()
        self.fade_overlay = FadeOverlay(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.root.add_widget(self.fade_overlay, index=100)

        self.add_background(self.root)
        self.add_buttons(self.root)

        self.add_widget(self.root)

        # keep track if we bound the touch event
        self._touch_bound = False

    def force_cleanup(self):
        try:
            gc.collect()
            gc.collect()
        except Exception:
            pass

    def schedule_periodic_cleanup(self):
        Clock.schedule_interval(lambda dt: self.force_cleanup(), 30)

    def add_background(self, root):
        with root.canvas.before:
            Color(0.1, 0.1, 0.1, 1)
            self.ui_rect = RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=self.update_ui_background, size=self.update_ui_background)

    def update_ui_background(self, instance, *args):
        self.ui_rect.pos = instance.pos
        self.ui_rect.size = instance.size

    # -- Video methods removed ----------------------------------------------
    # add_video_player, play_intro_video, on_click_next_video,
    # transition_video, on_sequence_video_end, play_loop_video
    # all commented out - videos no longer used in this screen.

    def add_buttons(self, root):
        panel_w = root.width * 0.50
        panel_h = root.height * 0.11
        panel_x = root.width / 2 - panel_w / 2
        self.panel_wrapper = Widget(size_hint=(None, None),
                                    size=(panel_w, panel_h),
                                    pos=(panel_x, 0))
        with self.panel_wrapper.canvas:
            Color(0.0, 0.0, 0.0, 0.4)
            self.button_panel = RoundedRectangle(size=self.panel_wrapper.size,
                                                 pos=self.panel_wrapper.pos,
                                                 radius=[25])
        root.bind(size=self.update_button_panel, pos=self.update_button_panel)
        root.add_widget(self.panel_wrapper)

        # CONTROLS button - centered at the bottom
        self.tutorial_button = HoverItem(
            size_hint=(0.18, 0.08),
            pos_hint={"center_x": 0.50, "center_y": 0.05},
            hoverSource="Graphics/Controls_Highlighted.png",
            defaultSource="Graphics/Controls.png",
            function=lambda x: self.show_tutorial()
        )

        # BACK button - goes to the LandingScreen (3-button main menu)
        self.home_button = HoverItem(
            size_hint=(0.10, 0.06),
            pos_hint={"right": 0.99, "y": 0.01},
            hoverSource="Graphics/Back_Highlighted.png",
            defaultSource="Graphics/Back.png",
            function=lambda x: self._go_home()
        )

        root.add_widget(self.tutorial_button)
        root.add_widget(self.home_button)

        self._build_tutorial_overlay(root)

    def _go_home(self):
        if self.manager:
            self.manager.current = "LandingScreen"

    # ------------------------------------------------------------------
    # Tutorial overlay
    # ------------------------------------------------------------------
    def _build_tutorial_overlay(self, root):
        import os as _os
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.boxlayout import BoxLayout
        from kivy.graphics import Line as _Line, Rectangle as _Rect

        _font = FONT_IMPACT

        overlay = _TutorialOverlay(
            size_hint=(0.97, 0.95),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            opacity=0,
        )

        with overlay.canvas.before:
            Color(0.02, 0.04, 0.10, 0.97)
            self._tut_bg = RoundedRectangle(pos=overlay.pos, size=overlay.size, radius=[18])
            Color(0.0, 0.75, 1.0, 0.85)
            self._tut_border = _Line(
                rounded_rectangle=(overlay.x, overlay.y, overlay.width, overlay.height, 18),
                width=2,
            )

        def _upd(inst, *_):
            self._tut_bg.pos  = inst.pos
            self._tut_bg.size = inst.size
            self._tut_border.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, 18)
        overlay.bind(pos=_upd, size=_upd)

        # -- Title (always visible at top) ----------------------------------
        title = Label(
            text="HOW TO USE",
            font_name=_font, font_size=30, bold=True,
            color=(0.3, 0.92, 1.0, 1),
            size_hint=(0.78, None), height=50,
            pos_hint={"x": 0.02, "top": 0.99},
            halign='left', valign='middle',
        )
        title.bind(size=title.setter('text_size'))
        overlay.add_widget(title)

        # -- GOT IT button (always visible top-right) -----------------------
        got_it = Button(
            text="CLOSE", font_name=_font, font_size=15,
            size_hint=(0.14, 0.07),
            pos_hint={"right": 0.99, "top": 0.99},
            background_normal='', background_color=(0.0, 0.45, 0.70, 1),
            color=(1, 1, 1, 1),
        )
        got_it.bind(on_press=lambda *_: self.show_tutorial())
        overlay.add_widget(got_it)

        # -- Scrollable content ---------------------------------------------
        scroll = ScrollView(
            size_hint=(0.97, 0.88),
            pos_hint={"center_x": 0.5, "y": 0.01},
            do_scroll_x=False,
        )
        content = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=14,
            padding=[28, 10, 28, 20],
        )
        content.bind(minimum_height=content.setter('height'))

        # -- Helpers --------------------------------------------------------
        def _header(text):
            lbl = Label(
                text=f"[b][color=00cfff]▸  {text}[/color][/b]",
                markup=True, font_name=_font, font_size=19,
                size_hint_y=None, height=34,
                halign='left', valign='middle', color=(1,1,1,1),
            )
            lbl.bind(size=lbl.setter('text_size'))
            return lbl

        def _body(text):
            lbl = Label(
                text=text, markup=True, font_size=15,
                size_hint_y=None,
                halign='left', valign='top',
                color=(0.84, 0.88, 0.93, 1),
                line_height=1.45,
            )
            def _sz(inst, val):
                inst.text_size = (val[0], None)
                inst.texture_update()
                inst.height = inst.texture_size[1] + 6
            lbl.bind(size=_sz)
            return lbl

        # -- Section data ---------------------------------------------------
        sections = [
            ("GETTING STARTED",
             "  • [b]Tap[/b] anywhere on the dark simulation area to [b]spawn a molecule[/b] with a random velocity.\n"
             "  • Press [b][color=00ff88]START[/color][/b] to begin — molecules move, bounce off walls and collide with each other.\n"
             "  • Press [b][color=ff6060]STOP[/color][/b] to pause and reset the simulation state.\n"
             "  • Press [b][color=aaaaaa]CLEAR[/color][/b] to remove all molecules from the canvas."),

            ("PRESETS  ◄ GAS · LIQUID · SOLID ►",
             "  • Click [b]◄ PRESETS ►[/b] (bottom-left) to open the preset picker.\n"
             "  • [b][color=00cfff]GAS[/color][/b] — 15 fast molecules, weak forces (ε=0.3), large spacing (σ=1.5).\n"
             "  • [b][color=00cfff]LIQUID[/color][/b] — 50 molecules, medium attraction (ε=2.0), random velocities.\n"
             "  • [b][color=00cfff]SOLID[/color][/b] — 275 molecules in a tight grid, strong bonds (ε=5.0), zero gravity.\n"
             "  • Press [b]CREATE[/b] to generate the chosen configuration instantly."),

            ("SLIDERS  (press WHY? to open panel)",
             "  • [b]Gravity[/b] — pulls molecules downward. 0 = weightless; 10 = dense atmosphere.\n"
             "  • [b]Epsilon (ε)[/b] — attraction depth. High values cause molecules to cluster (liquid/solid phases).\n"
             "  • [b]Sigma (σ)[/b] — spacing scale. Sets where repulsion flips to attraction (at 1.12 × σ).\n"
             "  • [b]Delta[/b] — physics timestep. Keep near 0.017 for stability; larger values cause chaos.\n"
             "  • [b]Speed[/b] — fast-forward rate. Does not change physics, only the clock rate.\n"
             "  • [b]Size[/b] — physical radius of each molecule on screen."),

            ("INTERMOLECULAR FORCES",
             "  • Press [b][color=00ff88]FORCES ON[/color][/b] to enable Lennard-Jones physics between molecules.\n"
             "  • [b][color=ff6030]Red/orange lines[/color][/b] — repulsive zone (r < 1.12σ, short-range r⁻¹² term dominates).\n"
             "  • [b][color=00cfff]Cyan/blue lines[/color][/b] — attractive zone (1.12σ to 2.5σ, r⁻⁶ pulls them together).\n"
             "  • No line = beyond 2.5σ cutoff — interaction is effectively zero.\n"
             "  • Press [b]LINES ON[/b] to toggle the visualisation without changing the physics.\n"
             "  • The [b]VECTORS[/b] icon draws force arrows on each molecule."),

            ("VERLET vs EULER INTEGRATION",
             "  • [b][color=00cfff]Verlet[/color][/b] — uses previous position to cancel integration errors. Energy stays stable long-term.\n"
             "  • [b][color=ffaa40]Euler[/color][/b] — simpler 'keep going' step. Errors accumulate — energy slowly drifts upward.\n"
             "  • Switch with the [b]Verlet-Off / Verlet-On[/b] button in the sliders panel.\n"
             "  • Watch the [b]stability badge[/b] (top-right) — Euler slowly drifts toward a warning; Verlet stays stable."),

            ("HARDWARE CONTROLLERS  (optional)",
             "  • An [b][color=00cfff]Arduino[/color][/b] accelerometer (USB or Wi-Fi bridge) injects kinetic energy when you shake it.\n"
             "  • Connection status for Arduino and Makey Makey appears in the bottom corners of the screen.\n"
             "  • [b]Makey Makey[/b] boards act as extra buttons — an on-screen key legend appears when one is detected."),
        ]

        for hdr, body in sections:
            content.add_widget(_header(hdr))
            content.add_widget(_body(body))

        scroll.add_widget(content)
        overlay.add_widget(scroll)

        self.tutorial_overlay = overlay
        root.add_widget(overlay)

    def show_tutorial(self):
        if not hasattr(self, "tutorial_overlay"):
            return
        overlay = self.tutorial_overlay
        if overlay.opacity < 0.5:
            # bring to front first
            if overlay.parent:
                overlay.parent.remove_widget(overlay)
                self.root.add_widget(overlay)
            Animation(opacity=1, duration=0.25).start(overlay)
        else:
            Animation(opacity=0, duration=0.20).start(overlay)

    def bring_buttons_to_front(self):
        for widget in [self.panel_wrapper, self.tutorial_button, self.home_button]:
            if widget.parent:
                self.root.remove_widget(widget)
            self.root.add_widget(widget)
        if hasattr(self, "tutorial_overlay") and self.tutorial_overlay.opacity > 0.05:
            overlay = self.tutorial_overlay
            if overlay.parent:
                overlay.parent.remove_widget(overlay)
            self.root.add_widget(overlay)

    def update_button_panel(self, *args):
        if hasattr(self, 'button_panel'):
            panel_w = self.root.width * 0.50
            panel_h = self.root.height * 0.11
            panel_x = self.root.width / 2 - panel_w / 2
            self.panel_wrapper.size = (panel_w, panel_h)
            self.panel_wrapper.pos = (panel_x, 0)
            self.button_panel.size = self.panel_wrapper.size
            self.button_panel.pos  = self.panel_wrapper.pos

    def on_touch_down_global(self, window, touch):
        return False

    def start_game(self):
        def switch_screen(*args):
            self.manager.current = "GameScreen"
        fade_out = Animation(opacity_level=1, duration=0.4)
        fade_out.bind(on_complete=switch_screen)
        fade_out.start(self.fade_overlay)

    def on_pre_leave(self, *args):
        pass

    def on_pre_enter(self, *args):
        # fade the black overlay away when entering this screen
        Animation(opacity_level=0, duration=0.5).start(self.fade_overlay)
        self.bring_buttons_to_front()

