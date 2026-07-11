from kivy.config import Config
# Drive input only from the OS-calibrated cursor. The raw multitouch device on
# the exhibit touchscreen reports mis-mapped coordinates (a left tap lands on
# the right), which fired the wrong buttons and spawned molecules in the wrong
# place. The touchscreen still works because X delivers it as a calibrated
# pointer that the mouse provider reads.
Config.remove_section('input')
Config.add_section('input')
Config.set('input', 'mouse', 'mouse,disable_multitouch')
Config.set('graphics', 'resizable', '1')

# Fix the window size BEFORE any module reads Window.height, because the UI scale
# is captured at import time and must match the final window size.
#
# The interface scales proportionally to the window, so it looks right at any
# size. Launch modes:
#   - default:            a resizable window sized to fit the user's screen
#                         (never oversized) - the right choice for a laptop/desktop
#   - MDKIVY_FULLSCREEN=1: fill the display at native resolution - use this on the
#                         large exhibit touchscreen
#   - MDKIVY_WIDTH / MDKIVY_HEIGHT: force an exact size, e.g.
#                         MDKIVY_WIDTH=3840 MDKIVY_HEIGHT=2160
import os as _os


def _fit_window_size():
    """A windowed size that fits the current screen but is never oversized.
    Falls back to a safe default if the screen size cannot be read."""
    try:
        import tkinter as _tk
        _r = _tk.Tk(); _r.withdraw()
        sw, sh = _r.winfo_screenwidth(), _r.winfo_screenheight()
        _r.destroy()
    except Exception:
        sw, sh = 1440, 900
    # 85% of the screen, clamped between the app minimum and a comfortable cap
    w = max(1054, min(1400, int(sw * 0.85)))
    h = max(713,  min(860,  int(sh * 0.85)))
    return w, h


_forced_w = _os.environ.get('MDKIVY_WIDTH')
_forced_h = _os.environ.get('MDKIVY_HEIGHT')
if _os.environ.get('MDKIVY_FULLSCREEN') == '1':
    Config.set('graphics', 'fullscreen', 'auto')
elif _forced_w and _forced_h:
    Config.set('graphics', 'width', _forced_w)
    Config.set('graphics', 'height', _forced_h)
else:
    _w, _h = _fit_window_size()
    Config.set('graphics', 'width', str(_w))
    Config.set('graphics', 'height', str(_h))

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition

# Below this size the HUD panels collide and the battle arena collapses
Window.minimum_width  = 1054
Window.minimum_height = 713
from mdkivy.screens.game_screen import GameScreen
from mdkivy.screens.start_screen import StartScreen
from mdkivy.screens.landing_screen import LandingScreen
from mdkivy.screens.battle_screen import BattleScreen
from mdkivy.screens.battle_name_screen import BattleNameScreen
from mdkivy.screens.leaderboard_screen import LeaderboardScreen


class WindowManager(ScreenManager):
    def __init__(self, **kwargs):
        self.landing_screen     = kwargs.pop("landing_screen")
        self.start_screen       = kwargs.pop("start_screen")
        self.game_screen        = kwargs.pop("game_screen")
        self.battle_screen      = kwargs.pop("battle_screen")
        self.battle_name_screen = kwargs.pop("battle_name_screen")
        self.leaderboard_screen = kwargs.pop("leaderboard_screen")

        super().__init__(**kwargs)
        self.transition = NoTransition()   # instant switch - no touch leaking between screens

        self.add_widget(self.landing_screen)
        self.add_widget(self.start_screen)
        self.add_widget(self.game_screen)
        self.add_widget(self.battle_screen)
        self.add_widget(self.battle_name_screen)
        self.add_widget(self.leaderboard_screen)

        self.current = self.landing_screen.name

    def switch_to_start_screen(self):
        self.current = self.start_screen.name

    def start_game(self, name):
        if name == self.start_screen.name:
            self.current = self.game_screen.name

    def go_back(self, name):
        if name == self.game_screen.name:
            self.current = self.landing_screen.name


class GameApp(App):
    def build(self):
        self.landing_screen     = LandingScreen(name="LandingScreen")
        self.start_screen       = StartScreen(name="StartScreen")
        self.game_screen        = GameScreen(name="GameScreen")
        self.battle_screen      = BattleScreen(name="BattleScreen")
        self.battle_name_screen = BattleNameScreen(name="BattleNameScreen")
        self.leaderboard_screen = LeaderboardScreen(name="LeaderboardScreen")
        self.window_manager = WindowManager(
            landing_screen=self.landing_screen,
            start_screen=self.start_screen,
            game_screen=self.game_screen,
            battle_screen=self.battle_screen,
            battle_name_screen=self.battle_name_screen,
            leaderboard_screen=self.leaderboard_screen,
        )
        return self.window_manager


if __name__ == "__main__":
    GameApp().run()
