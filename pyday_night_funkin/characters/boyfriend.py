
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import ANIMATION_TAG


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		anims = load_asset(ASSET.XML_BOYFRIEND)
		story_menu_char_anims = load_asset(ASSET.XML_STORY_MENU_CHARACTERS)

		self.animation.add_from_frames(
			"idle", anims["BF idle dance"], 24, True, (-5, 0),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_from_frames(
			"sing_note_left", anims["BF NOTE LEFT"], 24, False, (12, -6),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"miss_note_left", anims["BF NOTE LEFT MISS"], 24, False, (12, 24),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_from_frames(
			"sing_note_down", anims["BF NOTE DOWN"], 24, False, (-10, -50),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"miss_note_down", anims["BF NOTE DOWN MISS"], 24, False, (-11, -19),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_from_frames(
			"sing_note_up", anims["BF NOTE UP"], 24, False, (-29, 27),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"miss_note_up", anims["BF NOTE UP MISS"], 24, False, (-29, 27),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_from_frames(
			"sing_note_right", anims["BF NOTE RIGHT"], 24, False, (-38, -7),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_from_frames(
			"miss_note_right", anims["BF NOTE RIGHT MISS"], 24, False, (-30, 21),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_from_frames("scared", anims["BF idle shaking"], 24, True, (-4, 0))
		self.animation.add_from_frames(
			"hey", anims["BF HEY!!"], 24, False, (7, 4), (ANIMATION_TAG.SPECIAL,)
		)
		self.animation.add_from_frames(
			"story_menu", story_menu_char_anims["BF idle dance white"],
			24, True, tags=(ANIMATION_TAG.STORY_MENU,)
		)
		self.animation.add_from_frames(
			"story_menu_confirm", story_menu_char_anims["BF HEY!!"],
			24, False, tags=(ANIMATION_TAG.STORY_MENU, ANIMATION_TAG.SPECIAL)
		)
		self.animation.add_from_frames(
			"game_over_ini", anims["BF dies"], 24, False, (37, 11), (ANIMATION_TAG.GAME_OVER,)
		)
		self.animation.add_from_frames(
			"game_over_loop", anims["BF Dead Loop"], 24, True, (37, 5), (ANIMATION_TAG.GAME_OVER,)
		)
		self.animation.add_from_frames(
			"game_over_confirm", anims["BF Dead confirm"], 24, False, (37, 69),
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
	def get_story_menu_transform() -> t.Tuple[Vec2, float]:
		return (Vec2(-80, 0), .9)

	@staticmethod
	def get_string() -> str:
		return "bf"
