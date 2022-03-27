
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.animation import AnimationFrame
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.core.types import Numeric


class DaddyDearest(Character):

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_DADDY_DEAREST)

		self.animation.add_by_prefix(
			"idle", "Dad idle dance", 24, True, tags=(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "Dad Sing Note LEFT", 24, False, (-10, 10),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "Dad Sing Note DOWN", 24, False, (0, -30),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "Dad Sing Note UP", 24, False, (-6, 50),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "Dad Sing Note RIGHT", 24, False, (0, 27),
			(ANIMATION_TAG.SING,)
		)

	# Idk why but if the original game says so
	@staticmethod
	def get_hold_timeout() -> "Numeric":
		return 6.1

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"Dad idle dance BLACK LINE",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,),
		)

	@staticmethod
	def get_story_menu_info() -> t.Tuple[Vec2, float]:
		return (Vec2(0, 0), .5)

	@staticmethod
	def get_string() -> str:
		return "dad"
