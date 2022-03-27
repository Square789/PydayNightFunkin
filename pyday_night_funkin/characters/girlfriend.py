
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.characters._base import FlipIdleCharacter
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.animation import AnimationFrame
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class Girlfriend(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_GIRLFRIEND)

		self.animation.add_by_prefix(
			"cheer", "GF Cheer", 24, False, tags=(ANIMATION_TAG.SPECIAL,)
		)
		self.animation.add_by_indices(
			"idle_left", "GF Dancing Beat", range(15), 24, False,
			(0, -9), (ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_indices(
			"idle_right", "GF Dancing Beat", range(15, 30), 24, False,
			(0, -9), (ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "GF left note", 24, False, (0, -19), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "GF Down Note", 24, False, (0, -20), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "GF Up Note", 24, False, (0, 4), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "GF Right Note", 24, False, (0, -20), (ANIMATION_TAG.SING,)
		)
		# Nice space at the end bro
		self.animation.add_by_prefix("scared", "GF FEAR ", 24, True, (-2, -17))

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"GF Dancing Beat WHITE",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,),
		)

	@staticmethod
	def get_story_menu_info() -> t.Tuple[Vec2, float]:
		return (Vec2(0, 0), .5)

	@staticmethod
	def get_string() -> str:
		return "gf"
