
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.core.types import Numeric


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_BOYFRIEND)

		self.animation.add_by_prefix(
			"idle", "BF idle dance", 24, True, (-5, 0),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "BF NOTE LEFT0", 24, False, (12, -6),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_left", "BF NOTE LEFT MISS", 24, False, (12, 24),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "BF NOTE DOWN0", 24, False, (-10, -50),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_down", "BF NOTE DOWN MISS", 24, False, (-11, -19),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "BF NOTE UP0", 24, False, (-29, 27),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_up", "BF NOTE UP MISS", 24, False, (-29, 27),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "BF NOTE RIGHT0", 24, False, (-38, -7),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_right", "BF NOTE RIGHT MISS", 24, False, (-30, 21),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix("scared", "BF idle shaking", 24, True, (-4, 0))
		self.animation.add_by_prefix(
			"hey", "BF HEY!!", 24, False, (7, 4), (ANIMATION_TAG.SPECIAL,)
		)
		self.animation.add_by_prefix(
			"game_over_ini", "BF dies", 24, False, (37, 11), (ANIMATION_TAG.GAME_OVER,)
		)
		self.animation.add_by_prefix(
			"game_over_loop", "BF Dead Loop", 24, True, (37, 5), (ANIMATION_TAG.GAME_OVER,)
		)
		self.animation.add_by_prefix(
			"game_over_confirm", "BF Dead confirm", 24, False, (37, 69),
			(ANIMATION_TAG.GAME_OVER,)
		)

	def update(self, dt: float) -> None:
		singing = self.animation.has_tag(ANIMATION_TAG.SING)
		missing = self.animation.has_tag(ANIMATION_TAG.MISS)
		if singing or missing:
			self.hold_timer += dt
		else:
			self.hold_timer = 0

		# If no keys are being held (dont_idle managed by the InGameScene) and the sing animation
		# has been running for a while now, move back to idling.
		if (
			self.hold_timer > self.scene.conductor.beat_duration * 0.001 and
			not self.dont_idle and singing
		):
			self.animation.play("idle")

		# If le epic fail animation ended, return to idling at a specific frame for some reason
		if missing and not self.animation.current.playing:
			self.animation.play("idle", True, 10)

		# Skip `Character.update` because it ruins everything
		# Admittedly this also ruins everything but you can blame the original code for that.
		super(Character, self).update(dt)

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu", "BF idle dance white", 24, True,
			tags = (ANIMATION_TAG.STORY_MENU,)
		)
		spr.animation.add_by_prefix(
			"story_menu_confirm", "BF HEY!!", 24, False,
			tags = (ANIMATION_TAG.STORY_MENU, ANIMATION_TAG.SPECIAL)
		)

	@staticmethod
	def get_story_menu_info() -> t.Tuple[t.Tuple["Numeric", "Numeric"], "Numeric", "Numeric"]:
		return ((100, 100), 1, .9)

	@staticmethod
	def get_string() -> str:
		return "bf"
