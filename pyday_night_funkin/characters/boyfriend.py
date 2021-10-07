
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG
from pyday_night_funkin.characters._base import Character

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSETS.XML.BOYFRIEND)

		self.animation.add(
			"idle_bop", anims["BF idle dance"], 24, True, (-5, 0),
			(ANIMATION_TAG.IDLE, )
		)
		self.animation.add(
			"sing_note_left", anims["BF NOTE LEFT"], 24, False, (12, -6),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add(
			"miss_note_left", anims["BF NOTE LEFT MISS"], 24, False, (12, 24),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add(
			"sing_note_down", anims["BF NOTE DOWN"], 24, False, (-10, -50),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add(
			"miss_note_down", anims["BF NOTE DOWN MISS"], 24, False, (-11, -19),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add(
			"sing_note_up", anims["BF NOTE UP"], 24, False, (-29, 27),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add(
			"miss_note_up", anims["BF NOTE UP MISS"], 24, False, (-29, 27),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add(
			"sing_note_right", anims["BF NOTE RIGHT"], 24, False, (-38, -7),
			(ANIMATION_TAG.SING, )
		)
		self.animation.add(
			"miss_note_right", anims["BF NOTE RIGHT MISS"], 24, False, (-30, 21),
			(ANIMATION_TAG.MISS, )
		)
		self.animation.add("hey", anims["BF HEY!!"], 24, False, (7, 4), (ANIMATION_TAG.SPECIAL, ))
