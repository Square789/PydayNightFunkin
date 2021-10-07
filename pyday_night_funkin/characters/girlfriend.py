
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.enums import ANIMATION_TAG


class Girlfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSETS.XML.GIRLFRIEND)

		self.animation.add(
			"idle_bop", anims["GF Dancing Beat"], 24, True, tags = (ANIMATION_TAG.IDLE, )
		)
