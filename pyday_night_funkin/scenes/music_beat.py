
from math import floor

from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.scenes._base import BaseScene


class MusicBeatScene(BaseScene):

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.conductor = Conductor()

		self.cur_step = 0
		self.cur_beat = 0

	def update(self, dt: float) -> None:
		super().update(dt)
		old_step = self.cur_step

		lc = self.conductor.last_bpm_change
		self.cur_step = lc.step_time + floor(
			(self.conductor.song_position - lc.song_time) / self.conductor.step_duration
		)
		self.cur_beat = floor(self.cur_step / 4)

		if old_step != self.cur_step:
			self.on_step_hit()

	def on_beat_hit(self) -> None:
		pass

	def on_step_hit(self) -> None:
		if self.cur_step % 4 == 0:
			self.on_beat_hit()
