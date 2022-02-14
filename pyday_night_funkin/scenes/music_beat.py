
from math import floor

from loguru import logger

from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.core.scene import BaseScene


class MusicBeatScene(BaseScene):

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.conductor = Conductor()

		self.cur_step: int = 0
		self.cur_beat: int = 0
		self._last_step: int = 0

	def update(self, dt: float) -> None:
		super().update(dt)

		# NOTE: When conductor is thrown off, may call on_step_hit
		# with same values twice. Logger should scream bloody murder then.

		lc = self.conductor.get_last_bpm_change()
		new_step = lc.step + floor(
			(self.conductor.song_position - lc.song_time) / self.conductor.step_duration
		)

		for tween_step in range(self.cur_step + 1, new_step + 1):
			if tween_step != self._last_step + 1:
				logger.warning(
					f"New step ({tween_step}) was not strictly 1 higher than "
					f"last step! ({self._last_step})"
				)
			self.cur_step = tween_step
			self.cur_beat = floor(tween_step // 4)
			self.on_step_hit()

	def on_beat_hit(self) -> None:
		pass

	def on_step_hit(self) -> None:
		self._last_step = self.cur_step
		if self.cur_step % 4 == 0:
			self.on_beat_hit()
