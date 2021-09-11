
import typing as t

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.asset_system import ASSETS

if t.TYPE_CHECKING:
	from pyday_night_funkin.level import Level


class Boyfriend(Character):
	def __init__(self, level: "Level", *args, **kwargs) -> None:
		super().__init__(level, *args, **kwargs)
		anims = ASSETS.XML.BOYFRIEND.load()
		self.add_animation("idle_bop", anims["BF idle dance"], 24, True, (-5, 0))
		self.add_animation("sing_note_left", anims["BF NOTE LEFT"], 24, False, (12, -6))
		self.add_animation("miss_note_left", anims["BF NOTE LEFT MISS"], 24, False, (12, 24))
		self.add_animation("sing_note_down", anims["BF NOTE DOWN"], 24, False, (-10, -50))
		self.add_animation("miss_note_down", anims["BF NOTE DOWN MISS"], 24, False, (-11, -19))
		self.add_animation("sing_note_up", anims["BF NOTE UP"], 24, False, (-29, 27))
		self.add_animation("miss_note_up", anims["BF NOTE UP MISS"], 24, False, (-29, 27))
		self.add_animation("sing_note_right", anims["BF NOTE RIGHT"], 24, False, (-38, -7))
		self.add_animation("miss_note_right", anims["BF NOTE RIGHT MISS"], 24, False, (-30, 21))

	def update_character(self, dt: float, dont_idle: bool) -> None:
		if self.current_animation.startswith("sing"):
			self.hold_timer += dt

		if (
			self.hold_timer >= self.hold_timeout * self.level.conductor.beat_duration * 0.001 and
			not dont_idle
		):
			self.hold_timer = 0.0
			self.play_animation("idle_bop")
