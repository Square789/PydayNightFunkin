
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

		# TODO: beat hit stuff

