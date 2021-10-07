
import typing as t

from pyday_night_funkin.graphics.pnf_sprite import PNFSprite

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class Character(PNFSprite):

	hold_timeout = 4.0

	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scene = scene

		self.hold_timer = 0.0

	def update_sprite(self, dt: float) -> None:
		super().update_sprite(dt)
		if self.animation.current is not None and self.animation.current_name.startswith("sing"):
			self.hold_timer += dt

		if self.hold_timer >= self.hold_timeout * self.scene.conductor.step_duration * 0.001:
			self.hold_timer = 0.0
			self.animation.play("idle_bop")
