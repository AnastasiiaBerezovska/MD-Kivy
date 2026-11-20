import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp
from mdkivy.widgets.CustomSlider import CustomSlider
from kivy.graphics import Color, Line
from mdkivy.widgets.performance_monitor import get_global_monitor
from mdkivy.paths import FONT_IMPACT
from mdkivy.font_sizes import (
    READOUT_LABEL_FONT_FRACTION,
    READOUT_VALUE_FONT_FRACTION,
    scaled_font_size,
)

_IMPACT = FONT_IMPACT


class SliderBox(BoxLayout):
    """Slider with a label and current value."""

    def __init__(self, label_text, min_value, max_value, default_value, step, callback,
                 info_text='', info_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        self.padding   = [10, 10, 10, 8]
        self.spacing   = 8

        short_name = label_text.split('(')[0].strip()

        header = BoxLayout(orientation='horizontal', size_hint=(1, None), height=26)
        self.header = header

        self.name_label = Label(
            text=short_name,
            font_size='20sp',
            bold=True,
            color=(0.85, 0.92, 1.0, 1),
            halign='left',
            valign='middle',
        )
        self.name_label.bind(size=self.name_label.setter('text_size'))

        self.value_label = Label(
            text=f'{default_value:.2f}',
            size_hint_x=None,
            font_size='15sp',
            bold=True,
            color=(0.0, 0.85, 1.0, 1),
            halign='right',
            valign='middle',
        )
        self.value_label.bind(texture_size=lambda inst, size: setattr(inst, 'width', size[0]))

        header.add_widget(self.name_label)
        header.add_widget(self.value_label)
        self.add_widget(header)

        self.slider = CustomSlider(
            min=min_value,
            max=max_value,
            value=default_value,
            step=step,
            track_image="Graphics/SliderTrack.png",
            thumb_image="Graphics/SliderThumb.png",
            size_hint=(1, None),
            height=34,
        )
        self.slider.bind(value=self._on_value)
        self.add_widget(self.slider)

        self.external_callback = callback

    def resize_ui(self, window_height):
        """Match game readout fonts and give larger screens larger drag targets."""
        self.name_label.font_size = scaled_font_size(window_height, READOUT_LABEL_FONT_FRACTION)
        self.value_label.font_size = scaled_font_size(window_height, READOUT_VALUE_FONT_FRACTION)
        # Measure the value without constraining it to its old header width.
        self.value_label.text_size = (None, None)
        self.value_label.texture_update()
        self.value_label.width = self.value_label.texture_size[0]
        self.header.height = max(dp(32), self.value_label.font_size * 1.4)
        self.header.spacing = max(dp(8), window_height * 0.008)
        self.padding = [0, 0, 0, max(dp(8), window_height * 0.008)]
        self.spacing = max(dp(8), window_height * 0.008)
        self.slider.height = max(dp(48), window_height * 0.052)
        self.slider.thumb_diameter = max(dp(28), window_height * 0.025)
        self.slider.track_height = max(dp(4), window_height * 0.004)

    def _on_value(self, instance, value):
        self.value_label.text = f'{value:.2f}'
        if self.external_callback:
            self.external_callback(value)
