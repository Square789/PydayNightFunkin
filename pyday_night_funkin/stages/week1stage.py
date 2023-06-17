
from pyday_night_funkin.stages.common import BaseGameBaseStage


class Week1Stage(BaseGameBaseStage):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.spawn_default_base_game_arena()

	def ready(self) -> None:
		super().ready()
		self.main_cam.x += 400.0


class BopeeboStage(Week1Stage):
	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.cur_beat % 8 == 7:
			self.boyfriend.animation.play("hey")


class FreshStage(Week1Stage):
	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if self.cur_beat in (16, 80):
			self.dancers[self.girlfriend].frequency = 2
		elif self.cur_beat in (48, 112):
			self.dancers[self.girlfriend].frequency = 1
