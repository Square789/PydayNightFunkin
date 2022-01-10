
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.types import Numeric


class DaddyDearest(Character):

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSET.XML_DADDY_DEAREST)
		story_menu_char_anims = load_asset(ASSET.XML_STORY_MENU_CHARACTERS)

		self.animation.add_from_frames(
			"idle_bop", anims["Dad idle dance"], 24, True, tags=(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["Dad Sing Note LEFT"], 24, False, (-10, 10),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["Dad Sing Note DOWN"], 24, False, (0, -30),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_up", anims["Dad Sing Note UP"], 24, False, (-6, 50),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["Dad Sing Note RIGHT"], 24, False, (0, 27),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"story_menu", story_menu_char_anims["Dad idle dance BLACK LINE"],
			24, True, tags=(ANIMATION_TAG.STORY_MENU,)
		)

	# Idk why but if the original game says so
	@staticmethod
	def get_hold_timeout() -> "Numeric":
		return 6.1

	@staticmethod
	def get_story_menu_transform() -> t.Tuple[Vec2, float]:
		return (Vec2(0, 0), .5)

	@staticmethod
	def get_string() -> str:
		return "dad"
