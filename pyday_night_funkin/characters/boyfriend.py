
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.graphics.pnf_sprite import PNFSprite

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class Boyfriend(Character):
	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(scene, *args, **kwargs)
		anims = load_asset(ASSETS.XML.BOYFRIEND)
		self.animation.add("idle_bop", anims["BF idle dance"], 24, True, (-5, 0))
		self.animation.add("sing_note_left", anims["BF NOTE LEFT"], 24, False, (12, -6))
		self.animation.add("miss_note_left", anims["BF NOTE LEFT MISS"], 24, False, (12, 24))
		self.animation.add("sing_note_down", anims["BF NOTE DOWN"], 24, False, (-10, -50))
		self.animation.add("miss_note_down", anims["BF NOTE DOWN MISS"], 24, False, (-11, -19))
		self.animation.add("sing_note_up", anims["BF NOTE UP"], 24, False, (-29, 27))
		self.animation.add("miss_note_up", anims["BF NOTE UP MISS"], 24, False, (-29, 27))
		self.animation.add("sing_note_right", anims["BF NOTE RIGHT"], 24, False, (-38, -7))
		self.animation.add("miss_note_right", anims["BF NOTE RIGHT MISS"], 24, False, (-30, 21))
		self.animation.add("hey", anims["BF HEY!!"], 24, False, (7, 4))

		self.dont_idle = False

	def update_sprite(self, dt: float) -> None:
		# Ugly, but this method is a copypaste with a conditional changed
		super(Character, self).update_sprite(dt)
		if self.animation.current is not None and self.animation.current_name.startswith("sing"):
			self.hold_timer += dt

		if (
			self.hold_timer >= self.hold_timeout * self.scene.conductor.step_duration * 0.001 and
			not self.dont_idle
		):
			self.hold_timer = 0.0
			self.animation.play("idle_bop")
