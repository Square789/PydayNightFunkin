
import typing as t

from pyday_night_funkin.characters import FlipIdleCharacter
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.core.animation import AnimationFrame


class SkidNPump(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_SKID_N_PUMP)

		self.animation.add_by_prefix(
			"sing_note_up", "spooky UP NOTE", 24, False, (-20, 26),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "spooky DOWN note", 24, False, (-50, -130),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "note sing left", 24, False, (130, -10),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "spooky sing right", 24, False, (-130, -14),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_indices(
			"idle_left", "spooky dance idle", [0, 2, 6], 12, False, (0, 0),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_indices(
			"idle_right", "spooky dance idle", [8, 10, 12, 14], 12, False, (0, 0),
			(ANIMATION_TAG.IDLE,)
		)

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"spooky dance idle BLACK LINES",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,)
		)
