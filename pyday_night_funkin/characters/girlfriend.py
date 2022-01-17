
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.characters._base import FlipIdleCharacter
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG


class Girlfriend(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSET.XML_GIRLFRIEND)
		story_menu_char_anims = load_asset(ASSET.XML_STORY_MENU_CHARACTERS)

		self.animation.add_from_frames(
			"cheer", anims["GF Cheer"], 24, False, tags=(ANIMATION_TAG.SPECIAL,)
		)
		self.animation.add_by_indices(
			"idle_left", anims["GF Dancing Beat"], range(15), 24, False,
			(0, -9), (ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_indices(
			"idle_right", anims["GF Dancing Beat"], range(15, 30), 24, False,
			(0, -9), (ANIMATION_TAG.IDLE,)
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["GF left note"], 24, False, (0, -19), (ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["GF Down Note"], 24, False, (0, -20), (ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_up", anims["GF Up Note"], 24, False, (0, 4), (ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["GF Right Note"], 24, False, (0, -20), (ANIMATION_TAG.SING,)
		)
		# Nice space at the end bro
		self.animation.add_from_frames("scared", anims["GF FEAR "], 24, True, (-2, -17))
		self.animation.add_from_frames(
			"story_menu", story_menu_char_anims["GF Dancing Beat WHITE"],
			24, True, tags=(ANIMATION_TAG.STORY_MENU,)
		)

	@staticmethod
	def get_story_menu_transform() -> t.Tuple[Vec2, float]:
		return (Vec2(0, 0), .5)

	@staticmethod
	def get_string() -> str:
		return "gf"
