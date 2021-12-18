
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.enums import ANIMATION_TAG


class DaddyDearest(Character):

	# Idk why but if the original game says so
	hold_timeout = 6.1

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSETS.XML.DADDY_DEAREST)

		self.animation.add_from_frames(
			"idle_bop", anims["Dad idle dance"], 24, True, tags=(ANIMATION_TAG.IDLE, )
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["Dad Sing Note LEFT"], 24, False, (-10, 10),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["Dad Sing Note DOWN"], 24, False, (0, -30),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"sing_note_up", anims["Dad Sing Note UP"], 24, False, (-6, 50),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["Dad Sing Note RIGHT"], 24, False, (0, 27),
			(ANIMATION_TAG.SING, )
		)
