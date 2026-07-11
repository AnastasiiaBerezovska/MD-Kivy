from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.slider import Slider
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.switch import Switch
from kivy.uix.spinner import Spinner
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle, Line, RoundedRectangle, PushMatrix, PopMatrix, Translate

# UI reference height: tracks the real window height so fonts and panels scale
# to the display (laptop or 4K). main.py fixes the window size before this import,
# so Window.height is already final here. The old code capped this at 1000px,
# which froze the whole UI at laptop scale on the 4K exhibit screen.
_UI_H = max(Window.height, 700)
_UI_S = _UI_H / 950.0            # scale factor for design-pixel sizes (design basis ~950px tall)


def _su(v):
    """Scale a design-pixel value (tuned at ~950 px height) to the current window height."""
    return v * _UI_S
from mdkivy.simulation.game_layout import GameLayout
from mdkivy.widgets.HoverItem import HoverItem
from mdkivy.widgets.TextBlurb import TextBlurb
from mdkivy.widgets.CustomSlider import CustomSlider
from mdkivy.widgets.SliderBox import SliderBox
from mdkivy.widgets.SpinnerBox import SpinnerBox
from mdkivy.widgets.usage_graph import CPUUsageGraph
from mdkivy.widgets.performance_monitor import PerformanceMonitor
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from mdkivy.widgets.usage_graph import CPUUsageGraph
from mdkivy.widgets.performance_monitor import PerformanceMonitor
from mdkivy.widgets.memory_usage import MemoryUsageGraph
from mdkivy.widgets.speedometer import Speedometer
from mdkivy.simulation.game_layout import GameLayout
from mdkivy.widgets.performance_monitor import PerformanceMonitor
from mdkivy.widgets.arduino_performance_graph import ArduinoGraph
from kivy.clock import Clock
from kivy.metrics import mm, dp
from mdkivy.inputs.makey_makey import MakeyMakeyMonitor, KEY_LEGEND
from mdkivy.simulation.energy_bar import EnergyBar
from mdkivy.simulation.energy_input import EnergyInputWidget
from mdkivy.simulation.stability_graph import StabilityGraph
from mdkivy.paths import FONT_IMPACT

Clock.max_iteration = 20   # default; 1000 caused freeze bursts on screen transition


class WindowManager(ScreenManager):
    pass

class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.name = "GameScreen"

        # Performance monitor
        self.monitor = PerformanceMonitor()

        # Layout for the entire screen
        self.root = FloatLayout(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})

        # Background
        self.add_background(self.root)

        # Arduino graph must exist before GameLayout, which references it
        self.arduino_graph = ArduinoGraph()

        # GameLayout with both the performance monitor and the Arduino graph
        self.game_area = GameLayout(
            performance_monitor=self.monitor,
            arduino_graph=self.arduino_graph,
            size_hint=(1.0, 1.0),          # fill the whole window so molecules float edge-to-edge
            pos_hint={'x': 0, 'y': 0}
        )

        self.root.add_widget(self.game_area)

        # Energy thermometer bar - foldable, to the right of the game area
        self._energy_bar_visible = False
        self.energy_bar = EnergyBar(game_area_ref=self.game_area)
        self.energy_bar.size_hint = (0.025, 0)    # collapsed by default
        self.energy_bar.opacity   = 0
        self.energy_bar.pos_hint  = {'x': 0.822, 'y': 0.26}
        # self.root.add_widget(self.energy_bar)   # Energy bar (thermometer) disabled
        self.game_area.energy_bar = self.energy_bar

        # small toggle button just above where the bar lives
        self.energy_bar_btn = Button(
            text='+',
            size_hint=(0.025, 0.032),
            pos_hint={'x': 0.822, 'y': 0.83},
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.3, 0.9, 1.0, 1),
            font_size='14sp',
            bold=True,
        )
        with self.energy_bar_btn.canvas.before:
            Color(0.04, 0.12, 0.20, 0.92)
            self._ebar_btn_bg = RoundedRectangle(
                pos=self.energy_bar_btn.pos,
                size=self.energy_bar_btn.size,
                radius=[(6, 6)] * 4,
            )
        self.energy_bar_btn.bind(
            pos=lambda *a: setattr(self._ebar_btn_bg, 'pos', self.energy_bar_btn.pos),
            size=lambda *a: setattr(self._ebar_btn_bg, 'size', self.energy_bar_btn.size),
        )
        self.energy_bar_btn.bind(on_press=lambda x: self._toggle_energy_bar())
        # self.root.add_widget(self.energy_bar_btn)   # Energy bar toggle disabled

        # Energy input widget (foldable, right panel)
        self.energy_input = EnergyInputWidget(game_area_ref=self.game_area)
        self.energy_input.size_hint = (0.14, 0)
        self.energy_input.opacity   = 0
        self.energy_input.pos_hint  = {'right': 0.99, 'top': 0.70}
        # self.root.add_widget(self.energy_input)   # Energy Input disabled

        self.energy_input_label = Label(
            text='[b]Energy Input[/b]',
            markup=True,
            font_size=_UI_H * 0.028,
            color=(1.0, 0.6, 0.2, 1),
            size_hint=(0.14, 0.04),
            pos_hint={'right': 0.99, 'top': 0.51},
            halign='center', valign='middle',
            opacity=0,
        )
        self.energy_input_label.bind(size=self.energy_input_label.setter('text_size'))
        # self.root.add_widget(self.energy_input_label)   # Energy Input label disabled

        self._energy_input_visible = False
        self.energy_input_btn = Button(
            text='+',
            size_hint=(0.04, 0.032),
            pos_hint={'right': 0.99, 'y': 0.48},
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(1.0, 0.65, 0.2, 1),
            font_size='15sp',
            bold=True,
        )
        with self.energy_input_btn.canvas.before:
            Color(0.20, 0.14, 0.06, 0.90)
            self._einput_btn_bg = RoundedRectangle(
                pos=self.energy_input_btn.pos,
                size=self.energy_input_btn.size,
                radius=[(10, 10)] * 4,
            )
        self.energy_input_btn.bind(
            pos=lambda *a: setattr(self._einput_btn_bg, 'pos', self.energy_input_btn.pos),
            size=lambda *a: setattr(self._einput_btn_bg, 'size', self.energy_input_btn.size),
        )
        self.energy_input_btn.bind(on_press=lambda x: self._toggle_energy_input())
        # energy_input_btn is not added to the root: the energy bar toggle controls both panels

        # Right side panel - FloatLayout for screen-size independent positioning
        
        # Speedometer - bottom-left
        self.speedometer = Speedometer(performance_monitor=self.monitor)
        self.speedometer.size_hint = (0.14, 0.20)
        self.speedometer.pos_hint = {'x': 0.01, 'y': 0.06}
        self.root.add_widget(self.speedometer)

        # "Computing Load" label above speedometer
        self.cpu_usage_label = Label(
            text="[b]Computing Load[/b]",
            markup=True,
            font_size=_UI_H * 0.028,
            color=(0.25, 0.52, 0.88, 1),
            size_hint=(0.20, 0.04),
            pos_hint={'center_x': 0.09, 'y': 0.272},
            halign='center',
            valign='middle',
            opacity=1
        )
        # Constrain wrapping by width only (not height), so the larger scaled
        # font can't get clipped to a single wrapped line ("Load").
        self.cpu_usage_label.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
        self.root.add_widget(self.cpu_usage_label)

        self._cpu_expanded = False
        self.speedometer.bind(on_touch_down=self._on_cpu_touch)

        # Arduino Graph (under CPU label) - starts collapsed
        self.arduino_graph.size_hint = (0.15, 0)
        self.arduino_graph.opacity = 0
        self.arduino_graph.pos_hint = {'right': 0.99, 'top': 0.62}
        # self.root.add_widget(self.arduino_graph)   # Arduino Energy Input disabled

        # Arduino Graph Label (under graph) - hidden until graph is expanded
        self.arduino_graph_label = Label(
            text="[b]Arduino Energy Input[/b]",
            markup=True,
            font_size=_UI_H * 0.030,
            color=(1, 1, 1, 1),
            size_hint=(0.15, 0.05),
            pos_hint={'right': 0.99, 'top': 0.41},
            halign='center',
            valign='middle',
            opacity=0
        )
        self.arduino_graph_label.bind(size=self.arduino_graph_label.setter('text_size'))
        # self.root.add_widget(self.arduino_graph_label)   # Arduino Energy Input label disabled

        # small toggle button at bottom-right - collapses/restores the arduino graph
        self._arduino_graph_visible = False
        self.arduino_toggle_btn = Button(
            text='+',
            size_hint=(0.04, 0.032),
            pos_hint={'right': 0.99, 'y': 0.115},
            background_normal='',
            background_color=(0, 0, 0, 0),   # fully transparent - we draw our own bg
            color=(0.78, 0.82, 0.95, 1),
            font_size='15sp',
            bold=True,
        )
        with self.arduino_toggle_btn.canvas.before:
            Color(0.16, 0.18, 0.26, 0.90)
            self._ard_btn_bg = RoundedRectangle(
                pos=self.arduino_toggle_btn.pos,
                size=self.arduino_toggle_btn.size,
                radius=[(10, 10), (10, 10), (10, 10), (10, 10)]
            )
        self.arduino_toggle_btn.bind(
            pos=lambda *a: setattr(self._ard_btn_bg, 'pos', self.arduino_toggle_btn.pos),
            size=lambda *a: setattr(self._ard_btn_bg, 'size', self.arduino_toggle_btn.size),
        )
        self.arduino_toggle_btn.bind(on_press=lambda x: self._toggle_arduino_graph())
        # self.root.add_widget(self.arduino_toggle_btn)   # Arduino Energy Input toggle disabled


        # Preset spinner in the controls
        self.add_preset_spinner(self.root)

        # other UI elements (sliders, buttons, etc)
        self.add_ui_elements(self.root)

        # CPU-reactive border glow - added after UI so it renders on top of toolbar edges
        self._build_border_glow(self.root)

        # Re-add settings panel last so it draws on top of the border and all other widgets
        self.root.remove_widget(self.ui_panel)
        self.root.add_widget(self.ui_panel)

        # Arduino connection status UI (bottom-left)
        # Arduino status with glowing text (no background box)
        self.arduino_status_container = FloatLayout(
            size_hint=(0.15, 0.035),
            pos_hint={'x': 0.005, 'y': 0.005}
        )
        
        # Status indicator dot with outline for glow effect
        self.arduino_indicator = Label(
            text="●",
            size_hint=(0.1, 1),
            pos_hint={'x': 0, 'center_y': 0.5},
            color=(1, 0.3, 0.3, 1),  # Red for disconnected
            font_size='16sp',
            halign='center',
            valign='middle',
            outline_width=2,
            outline_color=(1, 0.3, 0.3, 0.5)  # Glow effect
        )
        self.arduino_status_container.add_widget(self.arduino_indicator)
        
        # Status text with outline for glow
        self.arduino_status_label = Label(
            text="Arduino: connecting…",
            size_hint=(0.9, 1),
            pos_hint={'x': 0.1, 'center_y': 0.5},
            color=(0.9, 0.9, 0.9, 1),
            font_size='11sp',
            halign='left',
            valign='middle',
            bold=True,
            outline_width=1,
            outline_color=(0.5, 0.5, 0.5, 0.3)
        )
        self.arduino_status_label.bind(size=self.arduino_status_label.setter('text_size'))
        self.arduino_status_container.add_widget(self.arduino_status_label)
        
        self.root.add_widget(self.arduino_status_container)

        self.add_widget(self.root)

        # Initial status reflects current connection
        self._update_arduino_status_label()
        self._ard_clock   = Clock.schedule_interval(lambda dt: self._update_arduino_status_label(), 2)
        self._makey_clock = None   # started in on_pre_enter

        # Background scan for Makey Makey boards (every 2 seconds)
        self.makey = MakeyMakeyMonitor()
        self._build_makey_status(self.root)
        self._makey_clock = Clock.schedule_interval(lambda dt: self._refresh_makey_ui(), 2)

        # Makey Makey press counters - one per board
        self._build_makey_counters(self.root)
        Clock.schedule_interval(lambda dt: self._refresh_makey_counters(), 0.1)


    def _build_makey_status(self, root):
        # Status row (bottom-right), mirroring the Arduino status at bottom-left:
        # right-aligned text with the indicator dot on the outer edge
        container = FloatLayout(
            size_hint=(0.22, 0.035),
            pos_hint={'right': 0.995, 'y': 0.005}
        )

        self.makey_dot = Label(
            text='●', size_hint=(0.08, 1), pos_hint={'right': 1, 'center_y': 0.5},
            color=(0.45, 0.45, 0.45, 1), font_size='16sp',
            halign='center', valign='middle',
            outline_width=2, outline_color=(0.3, 0.3, 0.3, 0.4)
        )
        self.makey_label = Label(
            text='Makey Makey: scanning…',
            size_hint=(0.92, 1), pos_hint={'x': 0, 'center_y': 0.5},
            color=(0.6, 0.6, 0.6, 1), font_size='11sp',
            halign='right', valign='middle', bold=True,
            outline_width=1, outline_color=(0.3, 0.3, 0.3, 0.2)
        )
        self.makey_label.bind(size=self.makey_label.setter('text_size'))
        container.add_widget(self.makey_dot)
        container.add_widget(self.makey_label)
        root.add_widget(container)

        # Key legend panel - fills the left-side gap under the Arduino graph
        # (y ~ 0.36) and above the button row (y ~ 0.09)
        self.makey_legend_container = FloatLayout(
            size_hint=(0.113, 0.33),
            pos_hint={'x': 0.005, 'y': 0.13},
            opacity=0
        )

        with self.makey_legend_container.canvas.before:
            Color(0.02, 0.06, 0.14, 0.97)
            self._legend_bg = RoundedRectangle(
                pos=self.makey_legend_container.pos,
                size=self.makey_legend_container.size,
                radius=[(10, 10), (10, 10), (10, 10), (10, 10)]
            )
            Color(0.0, 0.75, 1.0, 0.85)
            self._legend_border = Line(
                rounded_rectangle=[
                    self.makey_legend_container.x,
                    self.makey_legend_container.y,
                    self.makey_legend_container.width,
                    self.makey_legend_container.height, 10
                ],
                width=1.8
            )
        self.makey_legend_container.bind(
            pos=self._update_legend_bg, size=self._update_legend_bg
        )

        legend_font = max(12, int(_UI_H * 0.020))
        self.makey_legend_label = Label(
            text='', markup=True,
            size_hint=(0.88, 0.92),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            font_size=f'{legend_font}sp',
            halign='left', valign='top',
            line_height=1.35,
        )
        self.makey_legend_label.bind(size=self.makey_legend_label.setter('text_size'))
        self.makey_legend_container.add_widget(self.makey_legend_label)
        root.add_widget(self.makey_legend_container)

    def _build_makey_counters(self, root):
        """Two side-by-side counter labels showing how many times each Makey Makey was pressed."""
        counter_row = BoxLayout(
            orientation='horizontal',
            size_hint=(0.70, 0.055),
            pos_hint={'center_x': 0.47, 'top': 0.88},
            spacing=8,
        )

        def _make_counter(label_text, color):
            lbl = Label(
                text=label_text,
                markup=True,
                font_size=_UI_H * 0.026,
                bold=True,
                color=color,
                halign='center', valign='middle',
                size_hint=(1, 1),
            )
            lbl.bind(size=lbl.setter('text_size'))
            return lbl

        self._makey_left_label  = _make_counter('[b]LEFT  Makey:  0[/b]',  (0.20, 0.85, 1.0, 1))
        self._makey_right_label = _make_counter('[b]RIGHT  Makey:  0[/b]', (1.0, 0.60, 0.15, 1))

    def _refresh_makey_counters(self):
        L = self.game_area.makey_left_count
        R = self.game_area.makey_right_count
        self._makey_left_label.text  = f'[b]LEFT  Makey:  {L}[/b]'
        self._makey_right_label.text = f'[b]RIGHT  Makey:  {R}[/b]'

    def _update_legend_bg(self, *args):
        """Keep the rounded background and border in sync with the container."""
        c = self.makey_legend_container
        self._legend_bg.pos  = c.pos
        self._legend_bg.size = c.size
        self._legend_border.rounded_rectangle = [c.x, c.y, c.width, c.height, 8]

    def _refresh_makey_ui(self):
        if self.makey.connected:
            self.makey_dot.color         = (0.3, 0.85, 1, 1)
            self.makey_dot.outline_color = (0.1, 0.6, 0.9, 0.7)
            device = self.makey.device_info or 'Connected'
            self.makey_label.text        = f'Makey Makey: {device}'
            self.makey_label.color       = (0.4, 0.9, 1, 1)

            title_font = max(14, int(_UI_H * 0.024))
            rows = [
                f'[b][size={title_font}][color=00cfff]KEY BINDINGS[/color][/size][/b]',
                '[color=1a5f7a]──────────────[/color]',
            ]
            for key, action in KEY_LEGEND:
                rows.append(
                    f'  [b][color=ffffff]{key}[/color][/b]'
                    f'  [color=4499bb]->[/color]'
                    f'  [color=ffa940]{action}[/color]'
                )
            self.makey_legend_label.text = '\n'.join(rows)
            self.makey_legend_container.opacity = 1

        else:
            self.makey_dot.color         = (0.45, 0.45, 0.45, 1)
            self.makey_dot.outline_color = (0.3, 0.3, 0.3, 0.3)
            self.makey_label.text        = 'Makey Makey: Not Connected'
            self.makey_label.color       = (0.55, 0.55, 0.55, 1)
            self.makey_legend_container.opacity = 0
            self.makey_legend_label.text = ''

    def _on_cpu_touch(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self._toggle_cpu_panel()
            return True

    def _toggle_cpu_panel(self):
        from kivy.animation import Animation
        if self._cpu_expanded:
            Animation(size_hint_x=0.14, size_hint_y=0.20, duration=0.25).start(self.speedometer)
            Animation(opacity=1, duration=0.20).start(self.cpu_usage_label)
            self._cpu_expanded = False
        else:
            Animation(size_hint_x=0.30, size_hint_y=0.38, duration=0.25).start(self.speedometer)
            Animation(opacity=0, duration=0.15).start(self.cpu_usage_label)
            self._cpu_expanded = True
            # the gauge grows upward past the Temperature readout; re-add it so it
            # draws above the stat labels instead of behind them
            self.root.remove_widget(self.speedometer)
            self.root.add_widget(self.speedometer)

    def _toggle_energy_bar(self):
        from kivy.animation import Animation
        if self._energy_bar_visible:
            (Animation(opacity=0, duration=0.15) + Animation(size_hint_y=0, duration=0.15)).start(self.energy_bar)
            (Animation(opacity=0, duration=0.15) + Animation(size_hint_y=0, duration=0.15)).start(self.energy_input)
            self.energy_input_label.opacity = 0
            self.energy_bar_btn.text = '+'
            self._energy_bar_visible = False
            self._stop_glow(self.query_verlet)   # hide hint when panel closes
        else:
            (Animation(size_hint_y=0.55, duration=0.20) + Animation(opacity=1, duration=0.15)).start(self.energy_bar)
            (Animation(size_hint_y=0.18, duration=0.15) + Animation(opacity=1, duration=0.15)).start(self.energy_input)
            self.energy_input_label.opacity = 1
            self.energy_bar_btn.text = '−'
            self._energy_bar_visible = True
            self._start_glow(self.query_verlet, color=(0.20, 1.0, 0.45))  # green

    def _toggle_energy_input(self):
        from kivy.animation import Animation
        if self._energy_input_visible:
            anim = Animation(opacity=0, duration=0.15) + Animation(size_hint_y=0, duration=0.15)
            anim.start(self.energy_input)
            self.energy_input_label.opacity = 0
            self.energy_input_btn.text = '+'
            self._energy_input_visible = False
        else:
            anim = Animation(size_hint_y=0.18, duration=0.15) + Animation(opacity=1, duration=0.15)
            anim.start(self.energy_input)
            self.energy_input_label.opacity = 1
            self.energy_input_btn.text = '−'
            self._energy_input_visible = True

    # Per-button glow, shared by the LJ and Verlet buttons

    def _start_glow(self, btn, color=(0.45, 0.20, 1.0)):
        """Start a pulsing glow on any query button. color = (r,g,b) of the halo."""
        btn._glow_phase = 0.0
        btn._glow_color_rgb = color
        if getattr(btn, '_glow_event', None) is None:
            btn._glow_event = Clock.schedule_interval(
                lambda dt: self._update_btn_glow(btn, dt), 1 / 20.0)

    def _stop_glow(self, btn):
        ev = getattr(btn, '_glow_event', None)
        if ev:
            ev.cancel()
            btn._glow_event = None
        for gc in btn._glow_colors:
            gc.a = 0
        btn._border_color.r = 0.15
        btn._border_color.g = 0.65
        btn._border_color.b = 1.0
        btn._border_color.a = 0.85
        btn.color = (0.0, 0.85, 1.0, 1)

    def _update_btn_glow(self, btn, dt):
        import math
        btn._glow_phase = getattr(btn, '_glow_phase', 0.0) + dt * 1.5
        t   = (math.sin(btn._glow_phase) + 1) / 2   # 0 -> 1
        r, g, b = getattr(btn, '_glow_color_rgb', (0.45, 0.20, 1.0))
        base = 0.10 + t * 0.20   # 0.10 -> 0.30
        for gc, factor in zip(btn._glow_colors, (0.38, 0.62, 0.88)):
            gc.r, gc.g, gc.b = r, g, b
            gc.a = base * factor
        c = btn._border_color
        c.r = min(r + 0.15 * t, 1.0)
        c.g = min(g + 0.15 * t, 1.0)
        c.b = min(b + 0.05 * t, 1.0)
        c.a = 0.50 + t * 0.50
        # text color pulselike toward the glow colour
        bright = 0.75 + t * 0.25
        btn.color = (min(r * bright + 0.0, 1.0),
                     min(g * bright + 0.1, 1.0),
                     min(b * bright, 1.0), 1)

    # LJ and Verlet shortcuts 
    def _start_lj_glow(self):
        self._start_glow(self.query_lennard_jones, color=(0.45, 0.20, 1.0))  # purple

    def _stop_lj_glow(self):
        self._stop_glow(self.query_lennard_jones)

    def _toggle_arduino_graph(self):
        from kivy.animation import Animation
        if self._arduino_graph_visible:
            # fade out first, then collapse height to zero
            anim = Animation(opacity=0, duration=0.15) + Animation(size_hint_y=0, duration=0.15)
            anim.start(self.arduino_graph)
            self.arduino_graph_label.opacity = 0
            self.arduino_toggle_btn.text = '+'
            self._arduino_graph_visible = False
        else:
            # expand height back to original, then fade in
            anim = Animation(size_hint_y=0.2, duration=0.15) + Animation(opacity=1, duration=0.15)
            anim.start(self.arduino_graph)
            self.arduino_graph_label.opacity = 1
            self.arduino_toggle_btn.text = '−'
            self._arduino_graph_visible = True

    def add_background(self, root):
        """Add a grey background and bind its size/position to root."""
        with root.canvas.before:
            Color(0.01, 0.01, 0.04, 1)  # Match game area dark navy so bar area blends in
            self.ui_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self.update_ui_background, size=self.update_ui_background)

    def update_ui_background(self, instance, *args):
        """Update background dynamically when the window size changes."""
        self.ui_rect.pos = instance.pos
        self.ui_rect.size = instance.size

    # -- CPU-reactive screen border glow -----------------------------------
    def _build_border_glow(self, root):
        import math as _m, time as _t
        from kivy.graphics import Rectangle as _Rect
        self._border_widget = Widget(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        root.add_widget(self._border_widget)

        _STRIPS = 28        # number of gradient strips per edge
        _DEPTH  = 38        # how many pixels deep the gradient reaches inward

        def _draw_border(dt):
            cpu = min(self.monitor._target_usage, 100)
            if cpu < 40:
                t = cpu / 40.0
                br, bg, bb = 0.05 + 0.95*t, 1.0, 0.05
            elif cpu < 70:
                t = (cpu - 40) / 30.0
                br, bg, bb = 1.0, 1.0 - 0.65*t, 0.05
            else:
                t = (cpu - 70) / 30.0
                br, bg, bb = 1.0, 0.35 - 0.35*t, 0.05

            # two overlapping sine waves -> organic breathing pulse
            now   = _t.time()
            pulse = 0.5 + 0.4 * _m.sin(now * 1.1) + 0.1 * _m.sin(now * 2.9)
            pulse = max(0.0, min(1.0, pulse))
            peak  = 0.18 + 0.37 * pulse   # swings from dim (0.18) to bright (0.55)

            w = self._border_widget.width
            h = self._border_widget.height
            x = self._border_widget.x
            y = self._border_widget.y
            s = _DEPTH / _STRIPS          # thickness of each strip

            self._border_widget.canvas.clear()
            with self._border_widget.canvas:
                for i in range(_STRIPS):
                    # quadratic falloff: bright at i=0, fades to 0 at i=_STRIPS
                    frac  = i / _STRIPS
                    alpha = peak * (1.0 - frac) ** 2.2
                    d     = i * s           # distance from edge
                    Color(br, bg, bb, alpha)
                    # bottom strip
                    _Rect(pos=(x,         y + d),         size=(w,   s))
                    # top strip
                    _Rect(pos=(x,         y + h - d - s), size=(w,   s))
                    # left strip
                    _Rect(pos=(x + d,     y),             size=(s,   h))
                    # right strip
                    _Rect(pos=(x + w-d-s, y),             size=(s,   h))

        self._border_event = Clock.schedule_interval(_draw_border, 1 / 30.0)

    def add_preset_spinner(self, root):
        # The preset spinner is part of the main bottom row; kept as a no-op hook
        pass

    def generated_selected_preset(self, preset):
        """when user selects a preset, generate that type of molecule config"""
        if preset == "Solid":
            self.game_area.generate_solid()
        elif preset == "Liquid":
            self.game_area.generate_liquid()
        elif preset == "Gas":
            self.game_area.generate_gas()

    def _make_query_btn(self, pos_hint, callback):
        """Small styled circle '?' button with embedded (initially hidden) glow layers."""
        import os as _os
        from kivy.graphics import Color, Ellipse, Line as GLine
        _font = FONT_IMPACT
        _sz = int(_UI_H * 0.055)   # fixed square size -> always circular
        btn = Button(
            text='?',
            size_hint=(None, None),
            width=_sz, height=_sz,
            pos_hint=pos_hint,
            background_normal='', background_color=(0, 0, 0, 0),
            color=(0.0, 0.85, 1.0, 1),
            font_name=_font,
        )
        with btn.canvas.before:
            # glow layers - drawn first so they sit behind the button face
            _gc1 = Color(0.1, 0.75, 1.0, 0)   # outermost, invisible until forces ON
            _ge1 = Ellipse(pos=(-1000, -1000), size=(0, 0))
            _gc2 = Color(0.2, 0.85, 1.0, 0)
            _ge2 = Ellipse(pos=(-1000, -1000), size=(0, 0))
            _gc3 = Color(0.4, 0.95, 1.0, 0)   # innermost
            _ge3 = Ellipse(pos=(-1000, -1000), size=(0, 0))
            # button face - more transparent dark fill
            Color(0.04, 0.10, 0.28, 0.40)
            _bg = Ellipse(pos=(-1000, -1000), size=(0, 0))
            _brd_color = Color(0.15, 0.65, 1.0, 0.85)
            _brd = GLine(ellipse=(-1000, -1000, 0, 0), width=1.5)

        btn._border_color = _brd_color
        btn._glow_colors  = [_gc1, _gc2, _gc3]
        btn._glow_ellipses = [_ge1, _ge2, _ge3]
        _offsets = [14, 9, 4]   # px margin per glow layer (outer -> inner)

        def _sync(*a):
            _bg.pos  = btn.pos
            _bg.size = btn.size
            _brd.ellipse = (btn.x, btn.y, btn.width, btn.height)
            btn.font_size = f'{max(9, int(btn.height * 0.52))}sp'
            for ge, off in zip(btn._glow_ellipses, _offsets):
                ge.pos  = (btn.x - off, btn.y - off)
                ge.size = (btn.width + off * 2, btn.height + off * 2)

        btn.bind(pos=_sync, size=_sync)
        btn.bind(on_press=lambda *a: callback())
        return btn

    def add_ui_elements(self, root):
        """add all the sliders and buttons and stuff"""
        # shared description label - shown when any slider ? is tapped
        self._slider_info_label = Label(
            text='',
            bold=True,
            font_size='14sp',
            color=(1, 1, 1, 1),
            halign='left', valign='middle',
            size_hint=(0.78, None),
            height=0, opacity=0,
            pos_hint={'center_x': 0.48, 'y': 0.10},
        )
        with self._slider_info_label.canvas.before:
            Color(0.04, 0.07, 0.15, 1.0)
            self._sil_bg = RoundedRectangle(
                pos=self._slider_info_label.pos,
                size=self._slider_info_label.size,
                radius=[(8, 8)] * 4,
            )
            Color(0.0, 0.60, 0.95, 0.85)
            self._sil_border = Line(
                rounded_rectangle=(
                    self._slider_info_label.x, self._slider_info_label.y,
                    self._slider_info_label.width, self._slider_info_label.height, 8,
                ),
                width=1.5,
            )
        def _sync_sil(*a):
            lbl = self._slider_info_label
            self._sil_bg.pos  = lbl.pos
            self._sil_bg.size = lbl.size
            self._sil_border.rounded_rectangle = (lbl.x, lbl.y, lbl.width, lbl.height, 8)
            lbl.text_size = (lbl.width - 20, None)
        self._slider_info_label.bind(pos=_sync_sil, size=_sync_sil)
        # added to root at the END so it renders on top of all buttons
        self._slider_info_root = root

        self.ui_panel = self.create_sliders()
        self.ui_panel.opacity = 1   # visible but off-screen (pos_hint right:2.0)
        self.ui_panel_visible = False
        bottom_row = self.create_bottom_controls()
        root.add_widget(self.ui_panel)
        root.add_widget(bottom_row)
        self.add_stat_labels(root)
        
        self.lennard_jones_text = TextBlurb(
            text=(
                "V(r) = 4*epsilon [(sigma/r)^12 - (sigma/r)^6]\n\n"
                "RED/ORANGE lines: repulsive zone -- molecules closer than 1.12*sigma. "
                "The short-range r^-12 term dominates, pushing them apart. "
                "Brighter = stronger repulsion.\n\n"
                "CYAN/BLUE lines: attractive zone -- distance 1.12*sigma to 2.5*sigma. "
                "The r^-6 term pulls them together. Brightest near equilibrium, "
                "fading toward the cutoff.\n\n"
                "No line: beyond 2.5*sigma cutoff -- interaction is zero.\n\n"
                "These are NOT rigid bonds! The clustering you see IS the physics -- "
                "molecules in a liquid cluster because attraction keeps pulling them back. "
                "Open WHY? and lower Epsilon to weaken the pull and watch them drift apart like a gas."
            ),
            parent_size_prop=(0.32, 0.36),
            # right edge aligned to 0.988 (same as the stability card), sitting
            # in the right column under the graph so it shows in a consistent spot
            parent_pos_prop=(0.828, 0.33))
        self.query_lennard_jones = self._make_query_btn(
            {"right": 0.99, "center_y": 0.33},
            lambda: self.toggle_info(self.lennard_jones_text))
        # glow state stored on each button itself - see _start_glow / _stop_glow

        self.verlet_text = TextBlurb(
            text=(
                "Both methods predict where a molecule moves next -- but they do it differently.\n\n"
                "EULER: takes the current speed and says 'just keep going'. "
                "Fast and simple, but small errors build up every step -- like rolling a ball "
                "and ignoring that gravity curves its path. Over time energy drifts upward.\n\n"
                "VERLET: also looks at WHERE the molecule was last step to correct the next move. "
                "This cancels most errors, keeping energy stable for much longer.\n\n"
                "Try it: switch to Euler and watch the energy bar slowly climb red on its own. "
                "Switch back to Verlet and it stabilises. Same molecules, different math."
            ),
            parent_size_prop=(0.28, 0.28),
            # right edge aligned to 0.988 to match the LJ popup and stability card
            parent_pos_prop=(0.848, 0.22))
        self.query_verlet = self._make_query_btn(
            {"right": 0.99, "center_y": 0.22},
            lambda: self.toggle_info(self.verlet_text))

        # Canvas-drawn cursor - clears every frame so it leaves no ghost marks.
        # Covers the whole screen so it can draw at any window coordinate.
        self.cursOr = Widget(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self._cursor_cx = -100.0   # off-screen until first mouse move
        self._cursor_cy = -100.0

        def _draw_cursor(dt):
            import math, time as _t
            self.cursOr.canvas.clear()
            cx, cy = self._cursor_cx, self._cursor_cy
            if cx < 0:   # mouse hasn't entered the window yet
                return
            pulse = (math.sin(_t.time() * 3.5) + 1) / 2   # 0 -> 1
            with self.cursOr.canvas:
                # outer soft glowing
                Color(1.0, 0.45, 0.05, 0.07 + pulse * 0.06)
                Ellipse(pos=(cx - 13, cy - 13), size=(26, 26))
                Color(1.0, 0.50, 0.05, 0.16 + pulse * 0.10)
                Ellipse(pos=(cx - 8,  cy - 8),  size=(16, 16))
                # main fill - orange, pulses 
                Color(1.0, 0.55, 0.08, 0.65 + pulse * 0.25)
                Ellipse(pos=(cx - 5,  cy - 5),  size=(10, 10))
                # bright warm center dot
                Color(1.0, 0.90, 0.55, 1.0)
                Ellipse(pos=(cx - 2,  cy - 2),  size=(4,  4))

        self._cursor_event = Clock.schedule_interval(_draw_cursor, 1 / 30.0)

        # query buttons (query_lennard_jones, query_verlet) are kept for glow logic
        # but not added to root - popups are triggered by the main buttons instead
        root.add_widget(self.lennard_jones_text)
        root.add_widget(self.verlet_text)

        # Phase-preset info popups - shown automatically when Solid/Liquid/Gas is pressed
        self.solid_text = TextBlurb(
            text=(
                "SOLID phase: attraction >> kinetic energy.\n\n"
                "Molecules are trapped in fixed positions by LJ attraction — they vibrate "
                "in place but can't escape their neighbours. "
                "The tight cluster you see IS a solid.\n\n"
                "Lower Epsilon slowly and watch it melt into a liquid."
            ),
            parent_size_prop=(0.34, 0.30),
            parent_pos_prop=(0.36, 0.66))
        self.liquid_text = TextBlurb(
            text=(
                "LIQUID phase: attraction ≈ kinetic energy.\n\n"
                "Molecules have just enough energy to slip past neighbours but keep "
                "pulling each other back. No fixed positions, but they stay close — like water.\n\n"
                "Raise Epsilon to freeze into solid. Lower it to evaporate into gas."
            ),
            parent_size_prop=(0.34, 0.30),
            parent_pos_prop=(0.36, 0.66))
        self.gas_text = TextBlurb(
            text=(
                "GAS phase: kinetic energy >> attraction.\n\n"
                "Molecules move so fast that LJ attraction can't hold them together. "
                "They fly across the box and bounce off walls — exactly like real gas molecules.\n\n"
                "Turn Forces ON and raise Epsilon to watch them condense into a liquid."
            ),
            parent_size_prop=(0.34, 0.30),
            parent_pos_prop=(0.36, 0.66))
        root.add_widget(self.solid_text)
        root.add_widget(self.liquid_text)
        root.add_widget(self.gas_text)

        # added last so it draws on top of all buttons and panels
        root.add_widget(self._slider_info_label)

        Window.bind(mouse_pos=self.mPos)
        root.add_widget(self.cursOr)

        self._build_stability_indicator(root)

    # ------------------------------------------------------------------
    # Stability / accuracy indicator  (small label + hover popup with graph)
    # ------------------------------------------------------------------
    def _build_stability_indicator(self, root):
        # Uses Kivy's default font (Roboto), matching the Settings panel.

        # -- collapsed pill (top-right) --------------------------------
        self._stab_pill = Label(
            text='',
            font_size=15, bold=True,
            size_hint=(0.135, 0.05),
            pos_hint={'right': 0.988, 'top': 0.74},
            halign='center', valign='middle',
            color=(0.3, 0.92, 0.45, 1),
        )
        with self._stab_pill.canvas.before:
            self._pill_fill   = Color(0.03, 0.12, 0.05, 0.92)
            self._pill_bg     = RoundedRectangle(
                pos=self._stab_pill.pos, size=self._stab_pill.size, radius=[(9, 9)] * 4)
            self._pill_bcol   = Color(0.3, 0.92, 0.45, 0.80)
            self._pill_border = Line(
                rounded_rectangle=(self._stab_pill.x, self._stab_pill.y,
                                   self._stab_pill.width, self._stab_pill.height, 9), width=1.5)
        def _sync_pill(*a):
            self._pill_bg.pos  = self._stab_pill.pos
            self._pill_bg.size = self._stab_pill.size
            self._pill_border.rounded_rectangle = (
                self._stab_pill.x, self._stab_pill.y,
                self._stab_pill.width, self._stab_pill.height, 9)
        self._stab_pill.bind(pos=_sync_pill, size=_sync_pill)
        self._stab_pill.bind(size=self._stab_pill.setter('text_size'))
        root.add_widget(self._stab_pill)

        # -- expanded card (top-right): fixed width, height follows the text.
        # Children are positioned in pixels by _layout_stab_card so there is no
        # empty space below the description regardless of how long it is.
        self._stab_popup = FloatLayout(
            size_hint=(0.34, None), height=dp(230),
            pos_hint={'right': 0.975, 'top': 0.76},
            opacity=0,
        )
        with self._stab_popup.canvas.before:
            self._sp_fill   = Color(0.02, 0.05, 0.12, 0.97)
            self._sp_bg     = RoundedRectangle(
                pos=self._stab_popup.pos, size=self._stab_popup.size, radius=[(10, 10)] * 4)
            self._sp_bcol   = Color(0.30, 0.92, 0.45, 0.80)
            self._sp_border = Line(
                rounded_rectangle=(self._stab_popup.x, self._stab_popup.y,
                                   self._stab_popup.width, self._stab_popup.height, 10), width=1.5)
        def _sync_popup(*a):
            self._sp_bg.pos  = self._stab_popup.pos
            self._sp_bg.size = self._stab_popup.size
            self._sp_border.rounded_rectangle = (
                self._stab_popup.x, self._stab_popup.y,
                self._stab_popup.width, self._stab_popup.height, 10)
        self._stab_popup.bind(pos=_sync_popup, size=_sync_popup)

        # title heading (worst-warning name)
        self._stab_title = Label(
            text='', font_size=22, bold=True, markup=True,
            size_hint=(None, None), halign='left', valign='middle', color=(1, 1, 1, 1),
        )
        self._stab_popup.add_widget(self._stab_title)

        # fold icon (collapses the card back to the pill), top-right corner
        self._stab_fold = self._make_fold_button()
        self._stab_fold.pos_hint = {}   # positioned manually in _layout_stab_card
        self._stab_fold.bind(on_press=lambda *a: self._collapse_stability())
        self._stab_popup.add_widget(self._stab_fold)

        # graph
        self._stab_graph = StabilityGraph(size_hint=(None, None))
        self._stab_popup.add_widget(self._stab_graph)

        # caption under the graph
        self._stab_caption = Label(
            text='Stability over time', font_size=14,
            size_hint=(None, None), halign='center', valign='middle',
            color=(0.65, 0.74, 0.88, 1),
        )
        self._stab_popup.add_widget(self._stab_caption)

        # description (its texture height drives the card height)
        self._stab_desc = Label(
            text='', font_size=18, italic=True,
            size_hint=(None, None), halign='left', valign='top',
            color=(0.80, 0.90, 1.0, 1), markup=True,
        )
        self._stab_popup.add_widget(self._stab_desc)

        self._stab_popup.bind(pos=self._layout_stab_card, size=self._layout_stab_card)

        root.add_widget(self._stab_popup)
        self._stab_popup_visible = False

        # tapping the pill expands the card; the fold icon collapses it
        self._stab_pill.bind(on_touch_down=self._on_stab_badge_touch)

        self._stab_clock = Clock.schedule_interval(lambda dt: self._refresh_stability_ui(), 1.0)

    # severity -> (text rgb, border rgb)
    _SEV_STYLE = {
        'low':    ((0.95, 0.88, 0.20), (0.80, 0.72, 0.10)),
        'medium': ((1.00, 0.65, 0.20), (0.85, 0.50, 0.10)),
        'high':   ((1.00, 0.32, 0.32), (0.85, 0.20, 0.20)),
    }
    _SEV_ORDER = {'high': 0, 'medium': 1, 'low': 2}
    _SEV_SCORE = {'high': 0.10, 'medium': 0.40, 'low': 0.70}

    def _make_fold_button(self):
        """Circular button with a window-restore glyph, used to collapse the card."""
        from kivy.metrics import dp
        btn = Button(size_hint=(None, None), size=(dp(44), dp(44)),
                     pos_hint={'right': 0.965, 'top': 0.965},
                     background_normal='Graphics/FoldIcon.png',
                     background_down='Graphics/FoldIcon.png',
                     border=(0, 0, 0, 0),
                     background_color=(1, 1, 1, 1))
        return btn

    def _layout_stab_card(self, *a):
        """Stack title / graph / caption / description from the top in pixels and
        size the card height to the text, so there is no empty space below it."""
        from kivy.metrics import dp
        c = self._stab_popup
        if c.width < 10:
            return
        pad, gap = dp(14), dp(9)
        inner_w  = c.width - pad * 2
        title_h  = dp(30)
        graph_h  = dp(150)
        cap_h    = dp(20)

        # measure the wrapped description height
        self._stab_desc.text_size = (inner_w, None)
        self._stab_desc.texture_update()
        desc_h = max(dp(24), self._stab_desc.texture_size[1])

        total_h = pad + title_h + gap + graph_h + gap + cap_h + gap + desc_h + pad
        if abs(c.height - total_h) > 1:
            c.height = total_h          # triggers another layout pass via bind
            return

        x, top = c.x, c.top
        self._stab_title.size = (inner_w - dp(30), title_h)
        self._stab_title.text_size = self._stab_title.size
        self._stab_title.pos  = (x + pad, top - pad - title_h)

        fb = self._stab_fold
        # centred on the card's top-right corner tip (card is inset from the
        # window edge, so the straddling disc stays fully visible)
        fb.pos = (c.right - fb.width * 0.5, top - fb.height * 0.5)

        gy = top - pad - title_h - gap - graph_h
        self._stab_graph.size = (inner_w, graph_h)
        self._stab_graph.pos  = (x + pad, gy)

        cy = gy - gap - cap_h
        self._stab_caption.size = (inner_w, cap_h)
        self._stab_caption.text_size = self._stab_caption.size
        self._stab_caption.pos  = (x + pad, cy)

        dy = cy - gap - desc_h
        self._stab_desc.size = (inner_w, desc_h)
        self._stab_desc.pos  = (x + pad, dy)

    def _on_stab_badge_touch(self, widget, touch):
        if not widget.collide_point(*touch.pos):
            return False
        if widget.opacity < 0.2:
            return False   # pill hidden (e.g. Settings drawer open) - ignore
        from kivy.animation import Animation as _Anim
        self._stab_popup_visible = True
        _Anim(opacity=0, duration=0.12).start(self._stab_pill)
        _Anim(opacity=1, duration=0.18).start(self._stab_popup)
        return True

    def _collapse_stability(self):
        from kivy.animation import Animation as _Anim
        self._stab_popup_visible = False
        _Anim(opacity=0, duration=0.15).start(self._stab_popup)
        _Anim(opacity=1, duration=0.18).start(self._stab_pill)

    def _set_stability_hidden(self, hidden):
        """Hide the whole indicator (used while the Settings drawer is open)."""
        if not hasattr(self, '_stab_pill'):
            return
        if hidden:
            self._stab_pill.opacity  = 0
            self._stab_popup.opacity = 0
            self._stab_popup_visible = False
        elif not self._stab_popup_visible:
            self._stab_pill.opacity = 1

    def _refresh_stability_ui(self):
        if not hasattr(self, '_stab_pill'):
            return
        warnings = self.game_area.get_stability_warnings()

        if not self.game_area.simulation_running:
            pill_txt = 'Stopped'
            title    = 'Simulation stopped'
            rgb      = (0.55, 0.55, 0.62)
            desc     = '[color=8899aa]Press START to run the simulation.[/color]'
            score    = 0.5
        elif not warnings:
            pill_txt = 'System Stable'
            title    = 'System Stable'
            rgb      = (0.30, 0.92, 0.45)
            desc     = '[color=4deb75]Numerical integration is stable; total energy is well conserved.[/color]'
            score    = 1.0
        else:
            worst = min(warnings, key=lambda w: self._SEV_ORDER.get(w['severity'], 9))
            sev   = worst['severity']
            title = worst['title']
            desc  = f'[color=cfe0f5]{worst["detail"]}[/color]'
            score = self._SEV_SCORE[sev]
            if sev == 'high':
                pill_txt = 'System Unstable!'
                rgb      = (1.0, 0.35, 0.35)
            else:
                pill_txt = 'Warning'
                rgb      = (1.0, 0.70, 0.20)

        # collapsed pill
        self._stab_pill.text  = pill_txt
        self._stab_pill.color = (*rgb, 1)
        self._pill_fill.rgba  = (rgb[0] * 0.14, rgb[1] * 0.14, rgb[2] * 0.14, 0.92)
        self._pill_bcol.rgba  = (*rgb, 0.85)

        # expanded card - bold coloured heading, lighter grey parenthetical
        hexc = '%02x%02x%02x' % tuple(int(c * 255) for c in rgb)
        if '(' in title:
            head, _, tail = title.partition('(')
            self._stab_title.text = (f'[b][color={hexc}]{head.strip()}[/color][/b]'
                                     f'  [size=15][color=9fb0c5]({tail}[/size]')
        else:
            self._stab_title.text = f'[b][color={hexc}]{title}[/color][/b]'
        self._sp_bcol.rgba   = (*rgb, 0.85)
        self._stab_desc.text = desc
        self._layout_stab_card()   # re-fit card height to the new text

        if hasattr(self, '_stab_graph'):
            self._stab_graph.feed_score(score)

    def _update_arduino_status_label(self):
        try:
            ard = self.game_area.arduino
            if ard and ((getattr(ard, 'serial_connection', None) and ard.serial_connection.is_open) or getattr(ard, 'sock', None)):
                info = getattr(ard, 'connection_info', None)
                mode = 'Wi‑Fi' if getattr(ard, 'sock', None) else 'Serial'
                if not info:
                    info = getattr(ard, 'port', 'unknown')
                self.arduino_status_label.text = f"Arduino: Connected ({mode})"
                # Green glowing text
                self.arduino_status_label.color = (0.4, 1, 0.4, 1)
                self.arduino_status_label.outline_color = (0.2, 0.8, 0.2, 0.6)
                # Green glowing dot
                self.arduino_indicator.color = (0.4, 1, 0.4, 1)
                self.arduino_indicator.outline_color = (0.2, 0.8, 0.2, 0.7)
            else:
                self.arduino_status_label.text = "Arduino: Not Connected"
                # Red glowing text
                self.arduino_status_label.color = (1, 0.5, 0.5, 1)
                self.arduino_status_label.outline_color = (0.8, 0.2, 0.2, 0.5)
                # Red glowing dot
                self.arduino_indicator.color = (1, 0.3, 0.3, 1)
                self.arduino_indicator.outline_color = (0.8, 0.2, 0.2, 0.6)
        except Exception:
            self.arduino_status_label.text = "Arduino: Not Connected"
            # Red glowing text
            self.arduino_status_label.color = (1, 0.5, 0.5, 1)
            self.arduino_status_label.outline_color = (0.8, 0.2, 0.2, 0.5)
            # Red glowing dot
            self.arduino_indicator.color = (1, 0.3, 0.3, 1)
            self.arduino_indicator.outline_color = (0.8, 0.2, 0.2, 0.6)

    def retry_arduino_connect(self):
        # Close the existing connection, then attempt to re-open without blocking the UI
        try:
            if self.game_area.arduino:
                self.game_area.arduino.close()
        except Exception:
            pass

        from mdkivy.inputs.arduino_reading import ArduinoReading
        try:
            self.game_area.arduino = ArduinoReading()
            print(f"[INFO] Arduino reconnected on {self.game_area.arduino.port}")
        except Exception as e:
            print(f"[WARNING] Arduino reconnect failed: {e}")
            self.game_area.arduino = None
        self._update_arduino_status_label()


    def mPos(self, window, pos):
        self._cursor_cx = pos[0]
        self._cursor_cy = pos[1]

    def _make_drawer_toggle(self, label_text, on_cb, off_cb, on_label="On", off_label="Off", desc_text=None):
        """Toggle row - label + [On][Off] buttons with active/inactive highlight."""
        import os as _os
        _font = FONT_IMPACT

        _TXT_ON  = (1.0, 1.0, 1.0, 1.0)
        _TXT_OFF = (0.30, 0.55, 0.90, 1.0)
        _BOX_BG  = (0.03, 0.06, 0.13, 1.0)
        _BOX_BD  = (0.12, 0.25, 0.55, 0.55)

        row_height = _su(310) if desc_text else _su(136)
        row = BoxLayout(orientation='vertical', size_hint=(1, None), height=row_height,
                        spacing=_su(6), padding=[_su(14), _su(10), _su(14), _su(10)])
        lbl = Label(text=label_text, font_size=_su(28), bold=True,
                    color=(1, 1, 1, 1), halign='left', valign='middle',
                    size_hint=(1, None), height=_su(34))
        lbl.bind(size=lbl.setter('text_size'))

        row.add_widget(Widget(size_hint=(1, None), height=_su(16)))  # spacer pushes buttons lower

        btn_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=_su(52), spacing=_su(4))

        def _make_btn(text):
            b = Button(text=text, font_size=_su(23), bold=True,
                       color=_TXT_OFF,
                       background_normal='', background_down='',
                       background_color=(0, 0, 0, 0),
                       size_hint=(None, 1), width=_su(120))
            with b.canvas.before:
                Color(*_BOX_BG)
                _bg = RoundedRectangle(pos=b.pos, size=b.size, radius=[10])
                Color(*_BOX_BD)
                _bd = Line(rounded_rectangle=(b.x, b.y, b.width, b.height, 10), width=1.0)
            def _sync(*_):
                _bg.pos = b.pos; _bg.size = b.size
                _bd.rounded_rectangle = (b.x, b.y, b.width, b.height, 10)
            b.bind(pos=_sync, size=_sync)
            return b

        on_btn  = _make_btn(on_label)
        off_btn = _make_btn(off_label)

        def _activate(is_on):
            on_btn.color  = _TXT_ON if is_on else _TXT_OFF
            off_btn.color = _TXT_ON if not is_on else _TXT_OFF

        def _press_on(btn, touch):
            if getattr(touch, 'button', 'left') != 'left': return
            if not btn.collide_point(*touch.pos): return
            _activate(True); on_cb()
        def _press_off(btn, touch):
            if getattr(touch, 'button', 'left') != 'left': return
            if not btn.collide_point(*touch.pos): return
            _activate(False); off_cb()
        on_btn.bind(on_touch_down=_press_on)
        off_btn.bind(on_touch_down=_press_off)

        btn_row.add_widget(on_btn)
        btn_row.add_widget(off_btn)
        btn_row.add_widget(Widget())
        row.add_widget(lbl)
        row.add_widget(btn_row)
        if desc_text:
            desc = Label(text=desc_text, font_size=_su(23), italic=True,
                         color=(0.75, 0.80, 1.0, 1.0), halign='left', valign='top',
                         size_hint=(0.88, None), height=_su(150))
            desc.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
            row.add_widget(Widget(size_hint=(1, None), height=_su(8)))
            row.add_widget(desc)
        return row

    def create_sliders(self):
        """Settings drawer - semi-transparent, smooth scrollable, exact target style."""
        pad = max(5, int(_UI_H * 0.007))
        _back_w = int(_UI_H * 0.10 * 1.8)
        self.back_button = self._make_top_btn("BACK", self.go_back)
        self.back_button.size_hint = (None, 1.45)
        self.back_button.width     = _back_w
        self.back_button.pos_hint  = {'center_y': -0.55}

        # outer panel - slides in/out; full window height so content can be at any y
        ui_panel = FloatLayout(
            size_hint=(0.36, 1.0),
            pos_hint={'right': 2.0, 'top': 1.0},
        )

        # background frame - independent height; extend it down by changing size_hint_y
        bg_w = Widget(
            size_hint=(1, 1.06),
            pos_hint={'x': 0, 'top': 1.0},
        )

        # content box - sits inside a ScrollView so it can never clip off the
        # bottom of the screen, whatever the resolution. Its height tracks its
        # children (minimum_height); the ScrollView provides the viewport.
        content = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            spacing=0, padding=[0, 0, 0, _su(24)],
        )
        content.bind(minimum_height=content.setter('height'))

        # 2-column slider grid - sizes to its rows so there is no empty gap below
        slider_grid = GridLayout(
            cols=2, rows=3,
            size_hint=(1, None),
            spacing=(_su(4), _su(20)),
            padding=[_su(8), _su(14), _su(8), _su(18)]
        )
        slider_grid.bind(minimum_height=slider_grid.setter('height'))

        # shared info popup - shows description for whichever slider '?' was tapped
        _active = [None]
        def _show_slider_info(text):
            from kivy.animation import Animation
            lbl = self._slider_info_label
            if lbl.text == text and lbl.height > 0:
                Animation(height=0, opacity=0, duration=0.12).start(lbl)
                lbl.text = ''
                _active[0] = None
            else:
                lbl.text = text
                _active[0] = text
                Animation(height=_su(80), opacity=1, duration=0.12).start(lbl)

        gravity_box = SliderBox(
            "Gravity (W increase, S decrease)",
            0, 10, 0, 0.01, self.game_area.set_gravity,
            info_text=(
                "Pulls all molecules downward. Drag up then click START — molecules fall and bounce off the floor. "
                "At 10 they pile up at the bottom like a dense atmosphere. "
                "Zero = weightless, molecules drift freely. "
                "Combine with Forces ON to see gravity compete with molecular attraction."
            ),
            info_callback=_show_slider_info,
            size_hint=(1, 1)
        )
        epsilon_box = SliderBox(
            "Epsilon (Potential Depth used for Lennard-Jones force between Molecules) (E increase, D decrease)",
            0, 100, 50, 0.5, self.game_area.set_epsilon,
            info_text=(
                "Best seen with Forces ON (bottom row). "
                "High epsilon = strong attraction = molecules clump into liquid/solid groups — cyan lines brighten and pull them together. "
                "Low epsilon = weak attraction = molecules drift apart like a gas. "
                "This one slider shows the difference between solid, liquid and gas phases!"
            ),
            info_callback=_show_slider_info,
        )
        sigma_box = SliderBox(
            "Sigma (Potential Distance used for Lennard-Jones force between Molecules) (R increase, F decrease)",
            0.1, 3, 1, 0.01, self.game_area.set_sigma,
            info_text=(
                "With Forces ON: sets where the attractive/repulsive boundary sits. "
                "Small sigma = molecules crowd tightly together. Large sigma = they need more personal space. "
                "Watch the line colours shift — the red/cyan boundary is always at 1.12 x sigma, so it moves as you drag."
            ),
            info_callback=_show_slider_info,
        )
        delta_box = SliderBox(
            "Delta (Timestep update for Verlet's Algorithm) (T increase, G decrease)",
            1 / 60.0, 1, 1 / 60.0, 1 / 60.0, self.game_area.set_delta,
            info_text=(
                "The physics timestep — the dangerous one! "
                "Large delta = each step jumps too far = errors pile up faster than they correct = simulation explodes. "
                "Keep near 0.02 for stable behaviour. Try dragging to 0.5 to watch the chaos, then reduce to recover. "
                "This is a real limitation of all fixed-step physics engines."
            ),
            info_callback=_show_slider_info,
        )
        speed_box = SliderBox(
            "Speed of Simulation (Y increase, H decrease)",
            0.1, 1, 1, 0.1, self.game_area.set_speed,
            info_text=(
                "Fast-forward for the simulation. Higher = more physics updates per second = everything plays out faster. "
                "Does NOT change the physics, only the clock rate — like pressing fast-forward on a video. "
                "Changing speed while stopped has no effect; start the simulation first."
            ),
            info_callback=_show_slider_info,
        )
        size_box = SliderBox(
            "Size of Molecules (U increase, J decrease)",
            0.2, 1, 0.7, 0.05, self.game_area.set_size,
            info_text=(
                "Physical radius of each molecule. Larger = molecules collide more often and are easier to see. "
                "Try Size=1 with a Solid preset — molecules immediately crowd and push each other strongly. "
                "Smaller = molecules can get very close before repelling, allowing tighter packing."
            ),
            info_callback=_show_slider_info,
        )

        # fixed height per slider so each fills its cell (no oversized rows / empty gap)
        for _b in (gravity_box, delta_box, epsilon_box, size_box, sigma_box, speed_box):
            _b.size_hint_y = None
            _b.height = _su(94)

        # 2-column order: Gravity|Delta, Epsilon|Size, Sigma|Speed
        slider_grid.add_widget(gravity_box)
        slider_grid.add_widget(delta_box)
        slider_grid.add_widget(epsilon_box)
        slider_grid.add_widget(size_box)
        slider_grid.add_widget(sigma_box)
        slider_grid.add_widget(speed_box)

        self.game_area.gravity_slider = gravity_box.slider
        self.game_area.epsilon_slider = epsilon_box.slider
        self.game_area.sigma_slider   = sigma_box.slider
        self.game_area.delta_slider   = delta_box.slider
        self.game_area.speed_slider   = speed_box.slider
        self.game_area.size_slider    = size_box.slider

        # keep HoverItem buttons for internal toggle logic (invisible)
        self.verlet_button = self.create_hover_button("Verlet-Off", self.toggle_verlet_mode)
        self.verlet_button.opacity = 0
        self.bonds_button = HoverItem(
            size_hint=(0, 0), opacity=0,
            hoverSource="Graphics/Vectors_Highlighted.png",
            defaultSource="Graphics/Vectors.png",
            function=lambda x: self.toggle_force_arrows()
        )

        # -- semi-transparent drawer background (on bg_w, independent of content) --
        with bg_w.canvas.before:
            Color(0.01, 0.03, 0.10, 1.0)   # opaque so the top control bar can't bleed through
            _drawer_bg = Rectangle(pos=bg_w.pos, size=bg_w.size)
            Color(0.20, 0.40, 0.80, 0.55)
            _drawer_border = Line(rectangle=(bg_w.x, bg_w.y,
                                             bg_w.width, bg_w.height), width=1.6)
        def _sync_drawer(*_):
            _drawer_bg.pos  = bg_w.pos;  _drawer_bg.size  = bg_w.size
            _drawer_border.rectangle = (bg_w.x, bg_w.y, bg_w.width, bg_w.height)
        bg_w.bind(pos=_sync_drawer, size=_sync_drawer)

        # -- header: "Settings" bold + x circle button ---------------------
        # "Settings" title - standalone, pinned to the very top of the panel
        hdr_lbl = Label(text="Settings", font_size=_su(46), bold=True,
                        color=(1, 1, 1, 1), halign='left', valign='middle',
                        size_hint=(0.75, None), height=_su(60),
                        pos_hint={'x': 0.04, 'top': 0.965})
        hdr_lbl.bind(size=hdr_lbl.setter('text_size'))

        # x close button - direct FloatLayout child so pos_hint is unambiguous
        close_btn = Button(text='×', font_size=_su(22), bold=True,
                           size_hint=(None, None), width=_su(46), height=_su(46),
                           pos_hint={'right': 0.97, 'top': 0.965},
                           background_normal='', background_color=(0, 0, 0, 0),
                           color=(0.90, 0.92, 1.0, 1))
        with close_btn.canvas.before:
            Color(0.10, 0.14, 0.26, 1)
            _cbg = Ellipse(pos=close_btn.pos, size=close_btn.size)
            Color(0.28, 0.48, 0.88, 0.80)
            _cbd = Line(ellipse=(close_btn.x, close_btn.y,
                                 close_btn.width, close_btn.height), width=1.8)
        def _sync_close(*_):
            _cbg.pos  = close_btn.pos; _cbg.size  = close_btn.size
            _cbd.ellipse = (close_btn.x, close_btn.y,
                            close_btn.width, close_btn.height)
        close_btn.bind(pos=_sync_close, size=_sync_close,
                       on_press=lambda *_: self.toggle_sliders())

        # -- Lines / Vectors / Verlet toggle rows --------------------------
        def _lines_on():
            if not self.game_area.bonds_visible:  self.toggle_lj_lines()
        def _lines_off():
            if self.game_area.bonds_visible:      self.toggle_lj_lines()
        def _vecs_on():
            if not self.game_area.forces_visible: self.toggle_force_arrows()
        def _vecs_off():
            if self.game_area.forces_visible:     self.toggle_force_arrows()
        def _verlet_on():
            if not self.game_area.use_verlet:     self.toggle_verlet_mode()
        def _verlet_off():
            if self.game_area.use_verlet:         self.toggle_verlet_mode()

        lines_row  = self._make_drawer_toggle("Lines",   _lines_on,  _lines_off)
        vecs_row   = self._make_drawer_toggle("Vectors", _vecs_on,   _vecs_off)
        verlet_row = self._make_drawer_toggle("Prediction Method", _verlet_off, _verlet_on, "Euler", "Verlet",
                                               desc_text="Verlet looks at where the molecule was last to correct the next move. This cancels most errors, keeping energy stable for much longer.")

        # BACK button on the left, then the toggle rows below
        back_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=_su(60))
        back_row.add_widget(Widget(size_hint_x=1))
        back_row.add_widget(self.back_button)
        content.add_widget(back_row)
        content.add_widget(lines_row)
        content.add_widget(vecs_row)
        content.add_widget(verlet_row)
        content.add_widget(Widget(size_hint=(1, None), height=_su(30)))
        content.add_widget(slider_grid)

        # Scrollable viewport for the settings body, so the sliders are always
        # reachable even when the content is taller than the screen.
        scroller = ScrollView(
            size_hint=(1, None), height=_UI_H * 0.88,
            pos_hint={'x': 0, 'top': 0.90},
            do_scroll_x=False, do_scroll_y=True,
            bar_width=_su(6), bar_color=(0.35, 0.55, 0.95, 0.7),
            bar_inactive_color=(0.35, 0.55, 0.95, 0.25),
            scroll_type=['bars', 'content'],
        )
        scroller.add_widget(content)

        ui_panel.add_widget(bg_w)
        ui_panel.add_widget(hdr_lbl)
        ui_panel.add_widget(close_btn)
        ui_panel.add_widget(scroller)

        # Block click-through to game_area: dispatch to children first, then consume.
        # Collide against bg_w so only the visible frame area blocks touches.
        from kivy.uix.floatlayout import FloatLayout as _FL
        import types
        def _block_down(touch):
            _FL.on_touch_down(ui_panel, touch)
            return bg_w.collide_point(*touch.pos)
        def _block_up(touch):
            _FL.on_touch_up(ui_panel, touch)
            return bg_w.collide_point(*touch.pos)
        ui_panel.on_touch_down = types.MethodType(lambda s, t: _block_down(t), ui_panel)
        ui_panel.on_touch_up   = types.MethodType(lambda s, t: _block_up(t),   ui_panel)

        return ui_panel
    
    def toggle_info(self, text):
        text.toggle_visibility()

    def toggle_sliders(self):
        """Slide the Settings drawer in/out from the right."""
        from kivy.animation import Animation
        if self.ui_panel_visible:
            Animation(pos_hint={'right': 2.0, 'top': 1.0}, duration=0.25,
                      t='out_cubic').start(self.ui_panel)
            self.ui_panel_visible = False
            self._set_stability_hidden(False)
        else:
            Animation(pos_hint={'right': 1.0, 'top': 1.0}, duration=0.25,
                      t='out_cubic').start(self.ui_panel)
            self.ui_panel_visible = True
            self._set_stability_hidden(True)
    
    def add_glow_effect(self):
        """Inner soft fill + outer border lines - glow inside and around WHY."""
        from kivy.graphics import Color, Line, RoundedRectangle
        from kivy.graphics.instructions import InstructionGroup

        # inner fill (canvas.before, drawn behind the button image)
        self._why_inner_group = InstructionGroup()
        self._why_inner_color = Color(0.35, 0.15, 1.0, 0.18)   # purple tint
        self._why_inner_rect  = RoundedRectangle(
            pos=self.presets_button.pos, size=self.presets_button.size,
            radius=[(4, 4)] * 4,
        )
        self._why_inner_group.add(self._why_inner_color)
        self._why_inner_group.add(self._why_inner_rect)
        self.presets_button.canvas.before.add(self._why_inner_group)

        # outer border lines (canvas.after, drawn over the button image)
        self._why_outer_group = InstructionGroup()
        self._why_glow_meta   = []   # (Color, base_alpha, Line, offset)
        # outer to inner: (r, g, b, base_alpha, line_width, px_offset)
        _layers = [
            (0.60, 0.10, 1.00, 0.20, 5.0, 6),   # purple outer - wide halo
            (0.20, 0.50, 1.00, 0.45, 2.5, 3),   # blue-purple mid
            (0.00, 0.85, 1.00, 0.75, 1.4, 1),   # cyan rim - tight and bright
        ]
        for r, g, b, base_a, lw, off in _layers:
            gc = Color(r, g, b, base_a)
            gl = Line(
                rounded_rectangle=(
                    self.presets_button.x - off, self.presets_button.y - off,
                    self.presets_button.width + off * 2, self.presets_button.height + off * 2,
                    4,
                ),
                width=lw,
            )
            self._why_outer_group.add(gc)
            self._why_outer_group.add(gl)
            self._why_glow_meta.append((gc, base_a, gl, off))
        self.presets_button.canvas.after.add(self._why_outer_group)

        self._why_glow_phase = 0.0
        self._why_glow_event = Clock.schedule_interval(self._update_why_glow, 1 / 20.0)
        self.presets_button.bind(pos=self._sync_why_glow, size=self._sync_why_glow)

    def _sync_why_glow(self, *args):
        self._why_inner_rect.pos  = self.presets_button.pos
        self._why_inner_rect.size = self.presets_button.size
        for gc, base_a, gl, off in self._why_glow_meta:
            gl.rounded_rectangle = (
                self.presets_button.x - off, self.presets_button.y - off,
                self.presets_button.width + off * 2, self.presets_button.height + off * 2,
                4,
            )

    def _update_why_glow(self, dt):
        import math
        self._why_glow_phase += dt * 1.1
        t = (math.sin(self._why_glow_phase) + 1) / 2   # 0 - 1
        # inner fill breathes subtly
        self._why_inner_color.a = 0.12 + t * 0.14   # 0.12 - 0.26
        # outer border lines pulse
        for (gc, base_a, gl, off), pulse in zip(self._why_glow_meta, (0.12, 0.22, 0.18)):
            gc.a = base_a + t * pulse

    def remove_glow_effect(self):
        if hasattr(self, '_why_glow_event') and self._why_glow_event:
            self._why_glow_event.cancel()
            self._why_glow_event = None
        for grp, canvas in (
            (getattr(self, '_why_inner_group', None), self.presets_button.canvas.before),
            (getattr(self, '_why_outer_group', None), self.presets_button.canvas.after),
        ):
            if grp:
                try:
                    canvas.remove(grp)
                except Exception:
                    pass
        self._why_inner_group = self._why_outer_group = None
        self._why_glow_meta = []
        self.presets_button.unbind(pos=self._sync_why_glow, size=self._sync_why_glow)

    _BTN_IDLE   = (0.30, 0.55, 0.90, 1.0)   # dim blue - off / idle
    _BTN_ACTIVE = (1.0,  1.0,  1.0,  1.0)   # bright white - on / active
    _BTN_ON_TEXTS = ('STOP', 'FORCES ON')    # texts that represent "on" state

    def _make_top_btn(self, text, callback, accent=(0.30, 0.50, 0.85), bold=True):
        """Top-bar button: white on press/active, dim-blue when idle."""
        btn = Button(
            text=text, font_size='22sp', bold=True,
            color=self._BTN_IDLE,
            background_normal='', background_down='',
            background_color=(0, 0, 0, 0),
            size_hint=(0.60, 1),
        )
        with btn.canvas.before:
            Color(0.04, 0.08, 0.20, 0.50)   # semi-transparent dark blue bg
            _bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[10])
            Color(0.15, 0.30, 0.65, 0.65)   # dark blue border
            _bd = Line(rounded_rectangle=(btn.x, btn.y, btn.width, btn.height, 10), width=1.0)
        def _sync(*_):
            _bg.pos = btn.pos; _bg.size = btn.size
            _bd.rounded_rectangle = (btn.x, btn.y, btn.width, btn.height, 10)
        def _on_press(inst, *a):
            inst.color = self._BTN_ACTIVE
            callback()
        def _on_release(inst, *a):
            inst.color = self._BTN_ACTIVE if inst.text in self._BTN_ON_TEXTS else self._BTN_IDLE
        btn.bind(pos=_sync, size=_sync, on_press=_on_press, on_release=_on_release)
        return btn

    def create_bottom_controls(self):
        """Top bar matching target layout."""
        bar_h         = _UI_H * 0.10
        _icon_sz      = int(bar_h * 1.15)
        _back_w       = int(bar_h * 1.8)
        _settings_w   = int(bar_h * 2.2)
        _forces_lbl_w = int(bar_h * 2.4)
        bar = BoxLayout(
            orientation='horizontal',
            size_hint=(1.0, None),
            height=bar_h,
            pos_hint={'x': 0, 'top': 1.0},
            spacing=dp(14), padding=[dp(4), dp(6), dp(4), dp(6)],
        )
        with bar.canvas.before:
            Color(0.02, 0.03, 0.07, 0.35)   # subtle, mostly transparent so molecules float behind the controls
            _bar_bg = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda *_: setattr(_bar_bg, 'pos', bar.pos),
                 size=lambda *_: setattr(_bar_bg, 'size', bar.size))

        # Lines toggle (hidden, driven from settings drawer)
        self.lj_lines_btn = Button(
            text='LINES  ON', size_hint=(None, 1), width=0, opacity=0,
            background_normal='', background_color=(0,0,0,0),
            color=(0.20,1.0,0.55,1), font_size='11sp', bold=True,
        )
        with self.lj_lines_btn.canvas.before:
            Color(0.04,0.14,0.10,0.92)
            self._lines_btn_bg = RoundedRectangle(
                pos=self.lj_lines_btn.pos, size=self.lj_lines_btn.size, radius=[(6,6)]*4)
        with self.lj_lines_btn.canvas.after:
            Color(0.20,0.85,0.55,0.70)
            self._lines_btn_border = Line(
                rounded_rectangle=(self.lj_lines_btn.x, self.lj_lines_btn.y,
                                   self.lj_lines_btn.width, self.lj_lines_btn.height, 6), width=1.4)
        self.lj_lines_btn.bind(
            pos =lambda *a: (setattr(self._lines_btn_bg,'pos',self.lj_lines_btn.pos),
                             setattr(self._lines_btn_border,'rounded_rectangle',
                                     (self.lj_lines_btn.x,self.lj_lines_btn.y,
                                      self.lj_lines_btn.width,self.lj_lines_btn.height,6))),
            size=lambda *a: (setattr(self._lines_btn_bg,'size',self.lj_lines_btn.size),
                             setattr(self._lines_btn_border,'rounded_rectangle',
                                     (self.lj_lines_btn.x,self.lj_lines_btn.y,
                                      self.lj_lines_btn.width,self.lj_lines_btn.height,6))),
        )
        self.lj_lines_btn.bind(on_press=lambda *a: self.toggle_lj_lines())

        # presets_button kept for glow/toggle_sliders logic (not shown in bar)
        self.presets_button = self.create_hover_button("Settings", self.toggle_sliders)
        self.presets_button.hoverSource   = "Graphics/Settings_Highlighted.png"
        self.presets_button.defaultSource = "Graphics/Settings.png"
        self.presets_button.source        = "Graphics/Settings.png"
        self.presets_button.opacity = 0

        # dummy objects kept for compatibility
        self.preset_activate = Widget(size_hint=(0,0), opacity=0)
        self.preset_spinner  = type('_Dummy', (), {
            'possibleValues': ["Solid","Liquid","Gas"], 'value': 0})()

        # -- shared helper: flexible button with rounded border -----------
        def _make_bar_btn(text, size_hint_x=1):
            b = Button(
                text=text, font_size='26sp', bold=True,
                background_normal='', background_down='', background_color=(0,0,0,0),
                color=(0.30, 0.55, 0.90, 1.0),
                size_hint=(size_hint_x, 0.86),
                pos_hint={'center_y': -0.22},
            )
            with b.canvas.before:
                _fc = Color(0.03, 0.06, 0.16, 0.30)
                _fr = RoundedRectangle(pos=b.pos, size=b.size, radius=[14])
                _bc = Color(0.18, 0.30, 0.60, 0.45)
                _bl = Line(rounded_rectangle=(b.x, b.y, b.width, b.height, 14), width=0.8)
            def _sync(inst, val, r=_fr, l=_bl):
                r.pos = inst.pos; r.size = inst.size
                l.rounded_rectangle = (inst.x, inst.y, inst.width, inst.height, 14)
            b.bind(pos=_sync, size=_sync)
            b._fill_c = _fc
            b._bord_c = _bc
            return b

        # -- 1. LEFT: Play/Pause + Reset (fixed icon sizes) ----------------
        bar.add_widget(Widget(size_hint=(None, 1), width=dp(8)))
        self.play_pause_button = HoverItem(
            size_hint=(None, None), width=_icon_sz, height=_icon_sz,
            pos_hint={'center_y': -0.22},
            hoverSource="Graphics/Play_Highlighted.png",
            defaultSource="Graphics/Play.png",
            function=lambda x: self._toggle_play_pause(),
        )
        self.start_stop_button = self.play_pause_button
        bar.add_widget(self.play_pause_button)
        bar.add_widget(Widget(size_hint=(None, 1), width=dp(0)))
        reset_btn = HoverItem(
            size_hint=(None, None), width=_icon_sz, height=_icon_sz,
            pos_hint={'center_y': -0.22},
            hoverSource="Graphics/ResetCircle_Highlighted.png",
            defaultSource="Graphics/ResetCircle.png",
            function=lambda x: self._reset_everything(),
        )
        self.reset_button = reset_btn
        bar.add_widget(reset_btn)

        # -- 2. MIDDLE: flexible section fills all remaining space ----------
        middle = BoxLayout(orientation='horizontal', size_hint=(1, 1), spacing=dp(10))
        bar.add_widget(middle)

        # Solid / Liquid / Gas
        self.preset_activate = Widget(size_hint=(0, 0), opacity=0)
        self.preset_spinner  = type('_Dummy', (), {
            'possibleValues': ["Solid", "Liquid", "Gas"], 'value': 0})()
        self._preset_buttons = []
        self._active_preset_btn = None
        _phase_popup_map = {'Solid': 'solid_text', 'Liquid': 'liquid_text', 'Gas': 'gas_text'}

        def _show_phase_popup(name):
            # Hide the other phase popups, then show this one. It stays open
            # until the user taps its close button (no auto-dismiss).
            for attr in _phase_popup_map.values():
                blurb = getattr(self, attr, None)
                if blurb:
                    blurb.hide()
            blurb = getattr(self, _phase_popup_map.get(name, ''), None)
            if blurb:
                blurb.show()

        for _preset_name in ("Solid", "Liquid", "Gas"):
            _pb = _make_bar_btn(_preset_name)
            self._preset_buttons.append(_pb)
            def _on_preset_press(inst, name=_preset_name):
                for _b in self._preset_buttons:
                    _b.color = (0.30, 0.55, 0.90, 1.0)
                inst.color = (1.0, 1.0, 1.0, 1.0)
                self._active_preset_btn = inst
                self.generated_selected_preset(name)
                _show_phase_popup(name)
            _pb.bind(on_press=_on_preset_press)
            middle.add_widget(_pb)

        # Forces label + On / Off
        middle.add_widget(Widget(size_hint=(None, 1), width=dp(20)))
        _forces_lbl = Label(text="Calculate Forces\nBetween Atoms:", color=(0.30, 0.55, 0.90, 1.0),
                             font_size='18sp', bold=True,
                             size_hint=(None, 1), width=_forces_lbl_w,
                             halign='right', valign='middle',
                             text_size=(_forces_lbl_w, None),
                             pos_hint={'center_y': -0.22})
        middle.add_widget(_forces_lbl)
        self._forces_on_seg  = _make_bar_btn("On",  size_hint_x=0.7)
        self._forces_off_seg = _make_bar_btn("Off", size_hint_x=0.7)
        self._forces_on_seg.bind(on_press=lambda *_: self._forces_seg_press(True))
        self._forces_off_seg.bind(on_press=lambda *_: self._forces_seg_press(False))
        middle.add_widget(self._forces_on_seg)
        middle.add_widget(self._forces_off_seg)
        self._update_forces_seg(False)

        # -- 3. RIGHT: Settings (fixed size) --------------------------------
        # BACK lives only in the settings drawer, not on the main game screen.
        self._settings_top_btn = self._make_top_btn("Settings", self.toggle_sliders)
        self._settings_top_btn.font_size = '26sp'
        self._settings_top_btn.size_hint = (None, 0.86)
        self._settings_top_btn.width     = _settings_w
        self._settings_top_btn.pos_hint  = {'center_y': -0.22}
        bar.add_widget(self._settings_top_btn)
        bar.add_widget(Widget(size_hint=(None, 1), width=dp(8)))

        return bar

    def _select_preset(self, name):
        self.generated_selected_preset(name)

    def _forces_on(self):
        if not self.game_area.intermolecular_forces:
            self.toggle_intermolecular_forces()

    def _forces_off(self):
        if self.game_area.intermolecular_forces:
            self.toggle_intermolecular_forces()

    def _update_forces_seg(self, forces_on):
        _BLUE  = (0.30, 0.55, 0.90, 1.0)   # inactive: blue text
        _WHITE = (1.0,  1.0,  1.0,  1.0)   # active: white text
        _BG     = (0.03, 0.06, 0.16, 0.30)
        _BD_DIM = (0.18, 0.30, 0.60, 0.45)
        _BD_ACT = (0.30, 0.50, 0.80, 0.75)
        on  = self._forces_on_seg
        off = self._forces_off_seg
        if forces_on:
            on.color  = _WHITE; on._fill_c.rgba  = _BG; on._bord_c.rgba  = _BD_ACT
            off.color = _BLUE;  off._fill_c.rgba = _BG; off._bord_c.rgba = _BD_DIM
        else:
            on.color  = _BLUE;  on._fill_c.rgba  = _BG; on._bord_c.rgba  = _BD_DIM
            off.color = _WHITE; off._fill_c.rgba = _BG; off._bord_c.rgba = _BD_ACT

    def _forces_seg_press(self, want_on):
        if want_on and not self.game_area.intermolecular_forces:
            self.toggle_intermolecular_forces()
            lj = getattr(self, 'lennard_jones_text', None)
            if lj:
                lj.show()
        elif not want_on and self.game_area.intermolecular_forces:
            self.toggle_intermolecular_forces()
            lj = getattr(self, 'lennard_jones_text', None)
            if lj:
                lj.hide()

    def _set_play_icon(self):
        btn = self.play_pause_button
        btn.hoverSource   = "Graphics/Play_Highlighted.png"
        btn.defaultSource = "Graphics/Play.png"
        btn.source = btn.hoverSource if btn.use else btn.defaultSource

    def _set_pause_icon(self):
        btn = self.play_pause_button
        btn.hoverSource   = "Graphics/PauseIcon_Highlighted.png"
        btn.defaultSource = "Graphics/PauseIcon.png"
        btn.source = btn.hoverSource if btn.use else btn.defaultSource

    def _toggle_play_pause(self):
        if self.game_area.simulation_running:
            self.game_area.stop_simulation()
            if getattr(self, '_stab_clock', None):
                self._stab_clock.cancel()
                self._stab_clock = None
            sg = getattr(self, '_stab_graph', None)
            if sg and getattr(sg, '_draw_event', None):
                sg._draw_event.cancel()
                sg._draw_event = None
            self._set_play_icon()
        else:
            self.game_area.start_simulation()
            if not getattr(self, '_stab_clock', None):
                self._stab_clock = Clock.schedule_interval(
                    lambda dt: self._refresh_stability_ui(), 2.0)
            sg = getattr(self, '_stab_graph', None)
            if sg and not getattr(sg, '_draw_event', None):
                sg._draw_event = Clock.schedule_interval(sg._draw, 1 / 30.0)
            self._set_pause_icon()

    def _pause_simulation(self):
        """Pause or resume the simulation without resetting state."""
        if self.game_area.simulation_running:
            self.game_area.stop_simulation()
            if getattr(self, '_stab_clock', None):
                self._stab_clock.cancel()
                self._stab_clock = None
            sg = getattr(self, '_stab_graph', None)
            if sg and getattr(sg, '_draw_event', None):
                sg._draw_event.cancel()
                sg._draw_event = None
        else:
            self.game_area.start_simulation()
            if not getattr(self, '_stab_clock', None):
                self._stab_clock = Clock.schedule_interval(
                    lambda dt: self._refresh_stability_ui(), 2.0)
            sg = getattr(self, '_stab_graph', None)
            if sg and not getattr(sg, '_draw_event', None):
                sg._draw_event = Clock.schedule_interval(sg._draw, 1 / 30.0)

    def _reset_everything(self):
        """Full reset - all molecules gone, all params + every toggle back to defaults."""
        self.game_area.reset_all_params()

        self._set_play_icon()
        self._update_forces_seg(False)
        for _b in getattr(self, '_preset_buttons', []):
            _b.color = (0.30, 0.55, 0.90, 1.0)
        self._active_preset_btn = None
        def _restore(btn, stem):
            btn.hoverSource   = f"Graphics/{stem}_Highlighted.png"
            btn.defaultSource = f"Graphics/{stem}.png"
            btn.source = btn.hoverSource if btn.use else btn.defaultSource
        _restore(self.verlet_button, "Verlet-Off")
        _restore(self.bonds_button,  "Vectors")

        from kivy.animation import Animation as _Anim
        self.lj_lines_btn.text = 'LINES  ON'
        _anim = _Anim(opacity=0, duration=0.15)
        _anim.bind(on_complete=lambda *_: (
            setattr(self.lj_lines_btn, 'size_hint', (None, 1)),
            setattr(self.lj_lines_btn, 'width', 0),
        ))
        _anim.start(self.lj_lines_btn)

        if not getattr(self, '_stab_clock', None):
            self._stab_clock = Clock.schedule_interval(
                lambda dt: self._refresh_stability_ui(), 2.0)
        sg = getattr(self, '_stab_graph', None)
        if sg and not getattr(sg, '_draw_event', None):
            sg._draw_event = Clock.schedule_interval(sg._draw, 1 / 30.0)

    def go_back(self):
        self.parent.go_back(self.name)

    def on_pre_leave(self, *args):
        """Stop simulation and all background clocks while off-screen."""
        self.game_area.stop_simulation()

        # cancel all periodic clocks - they must not run on other screens
        for attr in ('_ard_clock', '_makey_clock', '_stab_clock', '_why_glow_event', '_border_event'):
            ev = getattr(self, attr, None)
            if ev:
                ev.cancel()
                setattr(self, attr, None)

        # pause stability graph draw loop
        if hasattr(self, '_stab_graph'):
            ev = getattr(self._stab_graph, '_draw_event', None)
            if ev:
                ev.cancel()
                self._stab_graph._draw_event = None

        # hide status labels so they don't bleed through other screens
        if hasattr(self, 'arduino_status_container'):
            self.arduino_status_container.opacity = 0
        if hasattr(self, 'makey_dot'):
            self.makey_dot.parent.opacity = 0

        if hasattr(self, '_cursor_event') and self._cursor_event:
            self._cursor_event.cancel()
            self._cursor_event = None
        self._set_play_icon()
        # collapse the stability card while off-screen; keep the pill state
        if hasattr(self, '_stab_popup'):
            self._stab_popup.opacity = 0
            self._stab_popup_visible = False
            self._stab_pill.opacity  = 1
        if hasattr(self, '_stab_pill'):
            self._refresh_stability_ui()

    def on_pre_enter(self, *args):
        """Restart background clocks and show status labels on re-entry."""
        # restart periodic clocks that were cancelled on leave
        if not getattr(self, '_ard_clock', None):
            self._ard_clock = Clock.schedule_interval(
                lambda dt: self._update_arduino_status_label(), 2)
        if not getattr(self, '_makey_clock', None):
            self._makey_clock = Clock.schedule_interval(
                lambda dt: self._refresh_makey_ui(), 2)
        if not getattr(self, '_stab_clock', None):
            self._stab_clock = Clock.schedule_interval(
                lambda dt: self._refresh_stability_ui(), 2.0)

        # restart stability graph draw loop
        if hasattr(self, '_stab_graph') and not getattr(self._stab_graph, '_draw_event', None):
            from kivy.clock import Clock as _C
            self._stab_graph._draw_event = _C.schedule_interval(
                self._stab_graph._draw, 1 / 30.0)

        # restart why-glow if it was cancelled
        if not getattr(self, '_why_glow_event', None) and hasattr(self, '_why_glow_meta'):
            self._why_glow_event = Clock.schedule_interval(self._update_why_glow, 1 / 20.0)

        # restart border glow
        if not getattr(self, '_border_event', None) and hasattr(self, '_border_widget'):
            self._build_border_glow(self.root)

        if hasattr(self, 'arduino_status_container'):
            self.arduino_status_container.opacity = 1
        if hasattr(self, 'makey_dot'):
            self.makey_dot.parent.opacity = 1
        if not getattr(self, '_cursor_event', None):
            from kivy.clock import Clock as _Clock
            import math, time as _t

            def _draw_cursor(dt):
                self.cursOr.canvas.clear()
                cx, cy = self._cursor_cx, self._cursor_cy
                if cx < 0:
                    return
                pulse = (math.sin(_t.time() * 3.5) + 1) / 2
                with self.cursOr.canvas:
                    Color(1.0, 0.45, 0.05, 0.07 + pulse * 0.06)
                    Ellipse(pos=(cx - 13, cy - 13), size=(26, 26))
                    Color(1.0, 0.50, 0.05, 0.16 + pulse * 0.10)
                    Ellipse(pos=(cx - 8,  cy - 8),  size=(16, 16))
                    Color(1.0, 0.55, 0.08, 0.65 + pulse * 0.25)
                    Ellipse(pos=(cx - 5,  cy - 5),  size=(10, 10))
                    Color(1.0, 0.90, 0.55, 1.0)
                    Ellipse(pos=(cx - 2,  cy - 2),  size=(4,  4))

            self._cursor_event = _Clock.schedule_interval(_draw_cursor, 1 / 30.0)

    def create_slider(self, label_text, min_value, max_value, default_value, step_value, callback):
        """Helper to create labeled sliders."""
        box = BoxLayout(orientation='horizontal')
        label = Label(text=label_text, size_hint=(0.3, None), height=10)
        if False:
            slider = Slider(min=min_value, max=max_value, value=default_value, step=step_value, size_hint=(0.7, None), height=10)
        else:
            slider = CustomSlider(
                min=min_value,
                max=max_value,
                value=default_value,
                step=step_value,
                track_image="Graphics/SliderTrack.png",
                thumb_image="Graphics/SliderThumb.png",
                slider_length=200,
                size_hint=(0.7,None),
                height=10
            )
        slider.bind(value=lambda instance, value: callback(value))
        box.add_widget(label)
        box.add_widget(slider)
        return box, slider

    def create_hover_button(self, label, callback):
        """Helper to create buttons with hover effects (responsive sizing)."""
        btn = HoverItem(
            size_hint=(1, 1),
            hoverSource=f"Graphics/{label}_Highlighted.png",
            defaultSource=f"Graphics/{label}.png",
            function=lambda x: callback()
        )
        with btn.canvas.after:
            Color(0.45, 0.48, 0.56, 0.85)
            border_rect = Line(rectangle=(btn.x, btn.y, btn.width, btn.height), width=1.5)
        def _update_border(*args):
            border_rect.rectangle = (btn.x, btn.y, btn.width, btn.height)
        btn.bind(pos=_update_border, size=_update_border)
        return btn
        
    def toggle_intermolecular_forces(self):
        """Toggle the usage of intermolecular forces."""
        from kivy.animation import Animation
        if self.game_area.intermolecular_forces:
            # currently ON - turning OFF
            self._update_forces_seg(False)
            self._stop_lj_glow()
            # fade out then collapse to zero width so no gap remains
            def _collapse(*a):
                self.lj_lines_btn.size_hint = (None, 1)
                self.lj_lines_btn.width = 0
            anim = Animation(opacity=0, duration=0.15)
            anim.bind(on_complete=_collapse)
            anim.start(self.lj_lines_btn)
        else:
            # currently OFF - turning ON
            self._update_forces_seg(True)
            self._start_lj_glow()
            # expand to proportional size then fade in
            self.lj_lines_btn.text  = 'LINES  ON'
            self.lj_lines_btn.color = (0.20, 1.0, 0.55, 1)
            self.lj_lines_btn.size_hint = (1, 1)   # join proportional layout
            Animation(opacity=1, duration=0.20).start(self.lj_lines_btn)
        self.game_area.toggle_intermolecular_forces()

    def toggle_lj_lines(self):
        """Hide or show LJ viz lines without touching force calculations."""
        if self.game_area.bonds_visible:
            self.game_area.toggle_lj_lines()          # turn lines OFF
            self.lj_lines_btn.text  = 'LINES  OFF'
            self.lj_lines_btn.color = (0.60, 0.60, 0.65, 1)   # dim when off
        else:
            self.game_area.toggle_lj_lines()          # turn lines ON
            self.lj_lines_btn.text  = 'LINES  ON'
            self.lj_lines_btn.color = (0.20, 1.0, 0.55, 1)    # bright green when on
        
    def toggle_force_arrows(self):
        """Toggle directional force arrows on molecules."""
        if self.game_area.forces_visible:
            self.bonds_button.hoverSource = "Graphics/Vectors_Highlighted.png"
            self.bonds_button.defaultSource = "Graphics/Vectors.png"
        else:
            self.bonds_button.hoverSource = "Graphics/Hide-Vecs_Highlighted.png"
            self.bonds_button.defaultSource = "Graphics/Hide-Vecs.png"
        self.bonds_button.source = self.bonds_button.hoverSource if self.bonds_button.use else self.bonds_button.defaultSource
        self.game_area.toggle_force_arrows()

    def toggle_forces_visible(self):
        """Toggle the visibility of forces."""
        if self.game_area.forces_visible:
            self.see_forces_button.hoverSource="Graphics/Show-Forces_Highlighted.png"
            self.see_forces_button.defaultSource="Graphics/Show-Forces.png"
            self.see_forces_button.source = self.see_forces_button.hoverSource if self.see_forces_button.use else self.see_forces_button.defaultSource
        else:
            self.see_forces_button.hoverSource="Graphics/Hide-Forces_Highlighted.png"
            self.see_forces_button.defaultSource="Graphics/Hide-Forces.png"
            self.see_forces_button.source = self.see_forces_button.hoverSource if self.see_forces_button.use else self.see_forces_button.defaultSource
        self.game_area.toggle_forces_visible()

    def toggle_simulation(self):
        """Toggle the simulation state. STOP resets fully; START begins fresh."""
        if self.game_area.simulation_running:
            self._set_play_icon()
            self.game_area.reset_simulation()
            self._update_forces_seg(False)
        else:
            self._set_pause_icon()
            self.game_area.start_simulation()
            
    def toggle_verlet_mode(self):
        """Toggle between Verlet and non-Verlet updates."""
        if self.game_area.use_verlet:
            self.verlet_button.hoverSource="Graphics/Verlet-On_Highlighted.png"
            self.verlet_button.defaultSource="Graphics/Verlet-On.png"
        else:
            self.verlet_button.hoverSource="Graphics/Verlet-Off_Highlighted.png"
            self.verlet_button.defaultSource="Graphics/Verlet-Off.png"
        self.verlet_button.source = self.verlet_button.hoverSource if self.verlet_button.use else self.verlet_button.defaultSource
        self.game_area.toggle_update_mode()

    def clear_game_area(self):
        """Clear the game area of all molecules and bonds."""
        self.game_area.clear_molecules()

    def add_stat_labels(self, root):
        """Stats stacked on the left side, overlaid on the game area."""
        fs_hdr = _UI_H * 0.034
        fs_val = _UI_H * 0.055

        def _hdr(text, color, pos_hint):
            l = Label(text=text, font_size=fs_hdr, bold=True, color=color,
                      size_hint=(0.20, 0.05), pos_hint=pos_hint,
                      halign='left', valign='bottom')
            l.bind(size=l.setter('text_size'))
            return l

        def _val(text, color, pos_hint):
            l = Label(text=text, font_size=fs_val, bold=True, color=color,
                      size_hint=(0.20, 0.07), pos_hint=pos_hint,
                      halign='left', valign='top')
            l.bind(size=l.setter('text_size'))
            return l

        # -- Total Energy --------------------------------------------------
        root.add_widget(_hdr("Total Energy", (1.0, 0.75, 0.3, 0.90),
                             {'x': 0.02, 'top': 0.72}))
        self.game_area.total_energy_label = _val(
            "0", (1.0, 0.6, 0.2, 1), {'x': 0.02, 'top': 0.670})
        root.add_widget(self.game_area.total_energy_label)

        # -- Pressure ------------------------------------------------------
        root.add_widget(_hdr("Pressure", (0.55, 0.9, 1.0, 0.90),
                             {'x': 0.02, 'top': 0.610}))
        self.game_area.pressure_label = _val(
            "0", (0.35, 0.85, 1.0, 1), {'x': 0.02, 'top': 0.560})
        root.add_widget(self.game_area.pressure_label)

        # -- Temperature ---------------------------------------------------
        root.add_widget(_hdr("Temperature", (1.0, 0.55, 0.75, 0.90),
                             {'x': 0.02, 'top': 0.500}))
        self.game_area.temperature_label = _val(
            "0", (1.0, 0.32, 0.55, 1), {'x': 0.02, 'top': 0.450})
        root.add_widget(self.game_area.temperature_label)


class MyApp(App):
    
    def build(self):
        self.window_manager = WindowManager()
        self.game_screen = GameScreen()
        self.window_manager.add_widget(self.game_screen)
        return self.window_manager

if __name__ == "__main__":
    MyApp().run()