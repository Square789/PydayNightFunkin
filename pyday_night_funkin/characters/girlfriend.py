
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.asset_system import ASSET, load_asset
from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.enums import ANIMATION_TAG


class Girlfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSET.XML_GIRLFRIEND)
		story_menu_char_anims = load_asset(ASSET.XML_STORY_MENU_CHARACTERS)

		self.animation.add_from_frames(
			"story_menu", story_menu_char_anims["GF Dancing Beat WHITE"],
			24, True, tags=(ANIMATION_TAG.STORY_MENU,)
		)

		self.animation.add_from_frames(
			"idle_bop", anims["GF Dancing Beat"], 24, True, tags=(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["GF left note"], 24, False, tags=(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["GF Down Note"], 24, False, tags=(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_up", anims["GF Right Note"], 24, False, tags=(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["GF Right Note"], 24, False, tags=(ANIMATION_TAG.SING,)
		)

	@staticmethod
	def get_story_menu_transform() -> t.Tuple[Vec2, float]:
		return (Vec2(0, 0), .5)

	@staticmethod
	def get_string() -> str:
		return "gf"
