
import typing as t

from pyday_night_funkin.stages.common import BaseGameBaseStage

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character


class TutorialStage(BaseGameBaseStage):
	def setup(self) -> None:
		super().setup()
		self.setup_default_base_game_arena()

	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("girlfriend", "main", char_cls, scene=self, x=400, y=130)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		# The og game has the rules (16 < self.cur_beat < 48 and self.cur_beat and
		# self.cur_beat % 16 == 15) here, but that has gf fire a beat too late.
		# i'm gonna do this, watch:
		if self.cur_beat == 30 or self.cur_beat == 46:
			self.opponent.animation.play("cheer", True)
		elif self.cur_beat == 31 or self.cur_beat == 47:
			self.boyfriend.animation.play("hey", True)
