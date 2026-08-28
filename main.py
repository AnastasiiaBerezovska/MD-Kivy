from kivy.config import Config
# use the calibrated pointer from the OS
Config.remove_section('input')
Config.add_section('input')
Config.set('input', 'mouse', 'mouse,disable_multitouch')
Config.set('graphics', 'resizable', '1')

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition

# keep the panels usable on smaller windows
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
        self.transition = NoTransition()

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
