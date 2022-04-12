
import typing as t

from pyday_night_funkin.enums import ANIMATION_TAG
from pyday_night_funkin.core.pnf_sprite import PNFSprite

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.types import Numeric
	from pyday_night_funkin.scenes import MusicBeatScene


class Character(PNFSprite):
	"""
	A beloved character that moves, sings and... well I guess that's
	about it. Holds some more information than a generic sprite which
	is related to the character via static `get_` methods.
	"""

	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scene = scene
		self._hold_timeout = self.get_hold_timeout()
		self.hold_timer = 0.0
		self.dont_idle = False

	def update(self, dt: float) -> None:
		super().update(dt)
		if (
			self.animation.has_tag(ANIMATION_TAG.SING) or
			self.animation.has_tag(ANIMATION_TAG.MISS)
		):
			self.hold_timer += dt

		if (
			self.hold_timer >= self._hold_timeout * self.scene.conductor.step_duration * 0.001 and
			not self.dont_idle
		):
			self.hold_timer = 0.0
			self.dance()

	def dance(self) -> None:
		"""
		Makes the character play their idle animation.
		Subclassable for characters that alternate between dancing
		poses, by default just plays an animation called `idle`.
		"""
		self.animation.play("idle")

	@staticmethod
	def get_hold_timeout() -> "Numeric":
		"""
		Returns how many steps the character should remain in their
		sing animation for after singing a note. Default is 4.
		"""
		return 4

	@staticmethod
	def initialize_story_menu_sprite(spr: PNFSprite) -> None:
		"""
		Initializes a sprite with story menu animations.
		It is expected that an animation called `story_menu` will be
		added. Also, `story_menu_confirm` is required for every story
		character appearing in the center (usually just bf.)
		"""
		raise NotImplementedError("Subclass this.")

	@staticmethod
	def transform_story_menu_sprite(spr: PNFSprite) -> None:
		"""
		Applies a transformation to the story menu sprite that makes it
		look acceptable enough.
		By default, sets the sprite offset to (100, 100), the scale
		to 214.5 / current frame width. [Parameters like that are
		probably an indicator i should loosen up how closely I want to
		be following the OG game's spaghetti.]
		"""
		spr.offset = (100, 100)
		# 214.5 is extracted as the default `width` of sprite 0, which is truth is kind of
		# a constant as Daddy Dearest will always be the character the story menu is created with.
		spr.scale = 214.5 / spr.get_current_frame_dimensions()[0]

	@staticmethod
	def get_string() -> str:
		"""
		Each character has a string assigned to them used to gather
		information for them, i. e. the health icon.
		This method returns that string. Default is `''`.
		"""
		return ""


class FlipIdleCharacter(Character):
	"""
	Character that does not play the `idle` animation in their
	`dance` function but instead alternates between `idle_left`
	and `idle_right` each invocation.
	"""

	_dance_right = False

	def dance(self) -> None:
		self._dance_right = not self._dance_right
		self.animation.play("idle_right" if self._dance_right else "idle_left")

