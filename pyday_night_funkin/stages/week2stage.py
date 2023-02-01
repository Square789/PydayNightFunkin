

from random import choice, randint
import typing as t

from pyday_night_funkin.base_game_pack import load_frames
from pyday_night_funkin.core.asset_system import load_sound
from pyday_night_funkin.stages.common import BaseGameBaseStage

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character


class Week2Stage(BaseGameBaseStage):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self._next_lightning_thresh = 0
		self._lightning_sounds = (
			load_sound("shared/sounds/thunder_1.ogg"),
			load_sound("shared/sounds/thunder_2.ogg"),
		)

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (
			"background", "girlfriend", "stage",
			("ui_combo", True), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
		)

	def setup(self) -> None:
		super().setup()

		self.background = self.create_object("background", "main", x=-200, y=-100)
		self.background.frames = load_frames("week2/images/halloween_bg.xml")
		# The masculine urge to steal the toothbrush of whoever names animations like that
		self.background.animation.add_by_prefix("idle", "halloweem bg0")
		self.background.animation.add_by_prefix(
			"lightning", "halloweem bg lightning strike", 24, False
		)
		self.background.animation.play("idle")

	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("stage", "main", char_cls, scene=self, x=100, y=300)

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
	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("stage", "main", char_cls, scene=self, x=100, y=230)
