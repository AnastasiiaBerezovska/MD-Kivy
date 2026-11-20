"""Shared font sizes for the simulation and two-player game screens."""

CONTROL_FONT_FRACTION = 0.025
BACK_FONT_FRACTION = 0.016
READOUT_LABEL_FONT_FRACTION = 0.015
READOUT_VALUE_FONT_FRACTION = 0.028
STAT_HEADING_FONT_FRACTION = 0.025


def scaled_font_size(window_height, fraction):
    """Return a pixel size that follows the window, with readable minimum text."""
    return max(9.0, window_height * fraction)
