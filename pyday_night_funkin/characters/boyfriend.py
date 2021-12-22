
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG
from pyday_night_funkin.characters._base import Character


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSETS.XML.BOYFRIEND)
		story_menu_char_anims = load_asset(ASSETS.XML.STORY_MENU_CHARACTERS)

		self.animation.add_from_frames(
			"story_menu", story_menu_char_anims["BF idle dance white"],
			24, True, tags=(ANIMATION_TAG.STORY_MENU, )
		)
		self.animation.add_from_frames(
			"story_menu_confirm", story_menu_char_anims["BF HEY!!"],
			24, False, tags=(ANIMATION_TAG.STORY_MENU, ANIMATION_TAG.SPECIAL)
		)

		self.animation.add_from_frames(
			"idle_bop", anims["BF idle dance"], 24, True, (-5, 0),
			(ANIMATION_TAG.IDLE, )
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["BF NOTE LEFT"], 24, False, (12, -6),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"miss_note_left", anims["BF NOTE LEFT MISS"], 24, False, (12, 24),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["BF NOTE DOWN"], 24, False, (-10, -50),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"miss_note_down", anims["BF NOTE DOWN MISS"], 24, False, (-11, -19),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add_from_frames(
			"sing_note_up", anims["BF NOTE UP"], 24, False, (-29, 27),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"miss_note_up", anims["BF NOTE UP MISS"], 24, False, (-29, 27),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["BF NOTE RIGHT"], 24, False, (-38, -7),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add_from_frames(
			"miss_note_right", anims["BF NOTE RIGHT MISS"], 24, False, (-30, 21),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add_from_frames(
			"hey", anims["BF HEY!!"], 24, False, (7, 4), (ANIMATION_TAG.SPECIAL, )
		)
