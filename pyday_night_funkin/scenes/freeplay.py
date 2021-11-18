
import typing as t

from pyday_night_funkin.alphabet import MenuTextLine
from pyday_night_funkin.asset_system import load_asset, ASSETS
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.enums import DIFFICULTY
from pyday_night_funkin.scenes.music_beat import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGameScene


class FreeplayScene(BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		from pyday_night_funkin.levels import WEEKS

		super().__init__(*args, **kwargs)

		self.bg = self.create_sprite("bg", image=load_asset(ASSETS.IMG.MENU_BG_BLUE))

		self.displayed_songs: t.List["InGameScene"] = []
		for week in WEEKS:
			self.displayed_songs.extend(week.levels)
		if not self.displayed_songs:
			raise RuntimeError("Panic at the FreeplayScene!")

		self._cur_selection = 0
		self._scroll_sound = load_asset(ASSETS.SOUND.MENU_SCROLL)
		self._text_lines: t.List[MenuTextLine] = []

		for i, lvl in enumerate(self.displayed_songs):
			m = MenuTextLine(
				i,
				CNST.GAME_DIMENSIONS,
				text = lvl.get_display_name(),
				bold = True,
				x = 0,
				y = 70*i + 30,
			)
			self._text_lines.append(m)
			self.add(m, "fg")

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.UP):
			self._change_selection(-1)

		if kh.just_pressed(CONTROL.DOWN):
			self._change_selection(1)

		if kh.just_pressed(CONTROL.BACKSPACE):
			from pyday_night_funkin.scenes.mainmenu import MainMenuScene
			self.game.set_scene(MainMenuScene)
			return # Don't want the ENTER block below to trigger when this one does

		if kh.just_pressed(CONTROL.ENTER):
			self.game.set_scene(
				self.displayed_songs[self._cur_selection],
				DIFFICULTY.HARD,
				FreeplayScene,
			)

	def _change_selection(self, by: int) -> None:
		self.sfx_ring.play(self._scroll_sound)
		self._cur_selection = (self._cur_selection + by) % len(self.displayed_songs)

		for i, line in enumerate(self._text_lines):
			line.opacity = 255 if i == self._cur_selection else 153
			line.target_y = i - self._cur_selection
