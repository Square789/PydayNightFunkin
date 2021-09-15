
import typing as t

from pyday_night_funkin.pnf_sprite import PNFSprite

if t.TYPE_CHECKING:
	from pyday_night_funkin.level import Level


class Character(PNFSprite):

	hold_timeout = 4.0

	def __init__(self, level: "Level", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.level = level

		self.hold_timer = 0.0

	# Unfortunately, the name `update` clashes with sprite, so have
	# this as a certified code smell
	def update_character(self, dt: float) -> None:
		if self.current_animation.startswith("sing"):
			self.hold_timer += dt

		if self.hold_timer >= self.hold_timeout * self.level.conductor.step_duration * 0.001:
			self.hold_timer = 0.0
			self.play_animation("idle_bop")
