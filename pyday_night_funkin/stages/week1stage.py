
import typing as t

from pyday_night_funkin.stages.common import BaseGameBaseStage

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character


class Week1Stage(BaseGameBaseStage):
	def setup(self) -> None:
		super().setup()
		self.setup_default_base_game_arena()

	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("stage", "main", char_cls, scene=self, x=100, y=100)


class BopeeboStage(Week1Stage):
	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.cur_beat % 8 == 7:
			self.boyfriend.animation.play("hey")
