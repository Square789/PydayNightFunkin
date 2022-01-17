
import typing as t

from pyday_night_funkin.characters import FlipIdleCharacter
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class SkidNPump(FlipIdleCharacter):
	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(scene, *args, **kwargs)

		anims = load_asset(ASSET.XML_SKID_N_PUMP)

		self.animation.add_from_frames(
			"sing_note_up", anims["spooky UP NOTE"], 24, False, (-20, 26),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["spooky DOWN note"], 24, False, (-50, -130),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["note sing left"], 24, False, (130, -10),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["spooky sing right"], 24, False, (-130, -14),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_indices(
			"idle_left", anims["spooky dance idle"], [0, 2, 6], 12, False,
			tags=(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_indices(
			"idle_right", anims["spooky dance idle"], [8, 10, 12, 14], 12, False,
			tags=(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_from_frames(
			"story_menu",
			load_asset(ASSET.XML_STORY_MENU_CHARACTERS)["spooky dance idle BLACK LINES"],
			24, True, tags=(ANIMATION_TAG.STORY_MENU,)
		)
