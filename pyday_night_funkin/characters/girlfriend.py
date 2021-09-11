
import typing as t

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.asset_system import ASSETS

if t.TYPE_CHECKING:
	from pyday_night_funkin.level import Level


class Girlfriend(Character):
	def __init__(self, level: "Level", *args, **kwargs) -> None:
		super().__init__(level, *args, **kwargs)
		anims = ASSETS.XML.GIRLFRIEND.load()
		self.add_animation("idle_bop", anims["GF Dancing Beat"], 24, True)

