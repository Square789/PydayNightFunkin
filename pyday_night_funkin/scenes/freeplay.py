
import typing as t

from pyday_night_funkin.scenes.music_beat import BaseScene


class FreeplayScene(BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		from pyday_night_funkin.levels import WEEKS

		super().__init__(*args, **kwargs)

		
