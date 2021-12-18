
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.scenes.music_beat import MusicBeatScene


class StoryMenuScene(MusicBeatScene):
	def __init__(self) -> None:
		self.mma = load_asset(ASSETS.XML.MAIN_MENU_ASSETS)

		self.campaign_chars = [
			self.create_sprite
		]

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")
