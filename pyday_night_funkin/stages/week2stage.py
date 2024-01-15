

from random import choice, randint

from pyglet.math import Vec2

from pyday_night_funkin.core.asset_system import load_frames, load_sound
from pyday_night_funkin.core.scene import OrderedLayer
from pyday_night_funkin.scenes.in_game import Anchor, AnchorAlignment as Al, InGameSceneKernel
from pyday_night_funkin.stages.common import BaseGameBaseStage


class Week2Stage(BaseGameBaseStage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				layers = (
					"background", "girlfriend", "stage", OrderedLayer("ui_combo"), "ui_arrows",
					"ui_notes", "ui0", "ui1", "ui2"
				),
				default_cam_zoom = 1.05,
				opponent_anchor = Anchor(Vec2(664, 831), Al.BOTTOM_RIGHT, "stage"),
			),
			*args,
			**kwargs,
		)

		# NOTE: This isolates behavior for them into this stage only with an id comp.
		# Maybe make a CharacterData property for this?
		if self.level_data.opponent_character == "skid_n_pump":
			self.dancers[self.opponent].frequency = 1

		self._next_lightning_thresh = 0
		self._lightning_sounds = (
			load_sound("shared/sounds/thunder_1.ogg"),
			load_sound("shared/sounds/thunder_2.ogg"),
		)

		self.background = self.create_object("background", "main", x=-200, y=-100)
		self.background.frames = load_frames("week2/images/halloween_bg.xml")
		# The masculine urge to steal the toothbrush of whoever names animations like that
		self.background.animation.add_by_prefix("idle", "halloweem bg0")
		self.background.animation.add_by_prefix(
			"lightning", "halloweem bg lightning strike", 24, False
		)
		self.background.animation.play("idle")

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if randint(0, 9) == 0 and self.cur_beat > self._next_lightning_thresh:
			# LIGHTNING BOLT, LIGHTNING BOLT!
			self.sfx_ring.play(choice(self._lightning_sounds))
			self.background.animation.play("lightning")

			self.boyfriend.animation.play("scared", True)
			self.girlfriend.animation.play("scared", True)

			self._next_lightning_thresh = self.cur_beat + randint(8, 24)


class MonsterStage(Week2Stage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				opponent_anchor = Anchor(Vec2(481, 921), Al.BOTTOM_RIGHT, "stage"),
			),
			*args,
			**kwargs,
		)
