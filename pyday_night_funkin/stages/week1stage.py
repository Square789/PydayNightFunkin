
from pyday_night_funkin.stages.common import BaseGameBaseStage


class Week1Stage(BaseGameBaseStage):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.spawn_default_base_game_arena()

class BopeeboStage(Week1Stage):
	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.cur_beat % 8 == 7:
			self.boyfriend.animation.play("hey")
