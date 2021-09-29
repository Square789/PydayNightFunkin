
import typing as t

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.asset_system import ASSETS, load_asset
if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class Girlfriend(Character):
	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(scene, *args, **kwargs)
		anims = load_asset(ASSETS.XML.GIRLFRIEND)
		self.add_animation("idle_bop", anims["GF Dancing Beat"], 24, True)
