
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin import scenes


class StoryMenuScene(scenes.MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.conductor.bpm = 102

		self.add(TextLine("Sorry nothing", bold=True, x=50, y=200))

		self.mma = load_asset(ASSETS.XML.MAIN_MENU_ASSETS)
		self.campaign_chars = []

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)
