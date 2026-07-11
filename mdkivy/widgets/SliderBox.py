import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.window import Window
from mdkivy.widgets.CustomSlider import CustomSlider
from kivy.graphics import Color, Line
from mdkivy.widgets.performance_monitor import get_global_monitor
from mdkivy.paths import FONT_IMPACT

_IMPACT = FONT_IMPACT

# Scale slider text/heights with the window so the drawer stays readable on a 4K
# exhibit screen as well as a laptop (design basis ~950 px tall).
_S = max(Window.height, 700) / 950.0


class SliderBox(BoxLayout):
    """Clean slider: label + live value above, slider below - no card border."""

    def __init__(self, label_text, min_value, max_value, default_value, step, callback,
                 info_text='', info_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding   = [10 * _S, 10 * _S, 10 * _S, 8 * _S]
        self.spacing   = 8 * _S

        short_name = label_text.split('(')[0].strip().split()[0].upper()

        # header row: name left, live value right
        header = BoxLayout(orientation='horizontal', size_hint=(1, None), height=26 * _S)

        self.name_label = Label(
            text=short_name,
            font_size=20 * _S,
            bold=True,
            color=(0.85, 0.92, 1.0, 1),
            halign='left',
            valign='middle',
        )
        self.name_label.bind(size=self.name_label.setter('text_size'))

        self.value_label = Label(
            text=f'{default_value:.2f}',
            font_size=15 * _S,
            bold=True,
            color=(0.0, 0.85, 1.0, 1),
            halign='right',
            valign='middle',
        )
        self.value_label.bind(size=self.value_label.setter('text_size'))

        header.add_widget(self.name_label)
        header.add_widget(self.value_label)
        self.add_widget(header)

        # slider
        self.slider = CustomSlider(
            min=min_value,
            max=max_value,
            value=default_value,
            step=step,
            track_image="Graphics/SliderTrack.png",
            thumb_image="Graphics/SliderThumb.png",
            size_hint=(1, None),
            height=34 * _S,
        )
        self.slider.bind(value=self._on_value)
        self.add_widget(self.slider)

        self.external_callback = callback

    def _on_value(self, instance, value):
        self.value_label.text = f'{value:.2f}'
        if self.external_callback:
            self.external_callback(value)
