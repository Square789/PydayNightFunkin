
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.enums import ANIMATION_TAG
from pyday_night_funkin.core.pnf_sprite import PNFSprite

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene
	from pyday_night_funkin.types import Numeric


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
		if self.animation.has_tag(ANIMATION_TAG.SING):
			self.hold_timer += dt

		if (
			self.hold_timer >= self._hold_timeout * self.scene.conductor.step_duration * 0.001 and
			not self.dont_idle
		):
			self.hold_timer = 0.0
			self.animation.play("idle_bop")

	@staticmethod
	def get_hold_timeout() -> "Numeric":
		"""
		Returns how many steps the character should remain in their
		sing animation for after singing a note. Default is 4.
		"""
		return 4

	@staticmethod
	def get_story_menu_transform() -> t.Tuple[Vec2, float]:
		"""
		Returns a two-element tuple of the translation and scale the
		character should undergo when its `story_menu` animation is
		displayed.
		"""
		return (Vec2(0, 0), 1)
