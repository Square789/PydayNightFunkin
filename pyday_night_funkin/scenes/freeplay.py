
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin.asset_system import load_asset, ASSETS
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin.scenes.music_beat import BaseScene


class FreeplayScene(BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		from pyday_night_funkin.levels import WEEKS

		super().__init__(*args, **kwargs)

		self.bg = self.create_sprite("bg", image=load_asset(ASSETS.IMG.MENU_BG_BLUE))

		self.displayed_songs = []
		for week in WEEKS:
			self.displayed_songs.extend(week.levels)

		for lvl in self.displayed_songs:
			pass # TODO

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")


	def update(self, dt: float) -> None:
		super().update(dt)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.UP):
			pass
