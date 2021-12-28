
import typing as t

from pyday_night_funkin.alphabet import MenuTextLine
from pyday_night_funkin.asset_system import load_asset, ASSET
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.enums import DIFFICULTY
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes


class FreeplayScene(scenes.BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		from pyday_night_funkin.levels import WEEKS

		super().__init__(*args, **kwargs)

		self.bg = self.create_object("bg", image=load_asset(ASSET.IMG_MENU_BG_BLUE))

		self.displayed_songs: t.List["scenes.InGameScene"] = []
		for week in WEEKS:
			self.displayed_songs.extend(week.levels)
		if not self.displayed_songs:
			raise RuntimeError("Panic at the FreeplayScene!")

		self._cur_selection = 0
		self._scroll_sound = load_asset(ASSET.SOUND_MENU_SCROLL)
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
			m.opacity = 153
			self._text_lines.append(m)
			self.add(m, "fg")

		self.menu = Menu(
			self.game.key_handler, len(self.displayed_songs), self._on_select, self._on_confirm
		)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)
			return # Don't want any menu callbacks to trigger when this block runs

		self.menu.update()

	def _on_select(self, i: int, state: bool) -> None:
		if state:
			self._text_lines[i].opacity = 255
			self.sfx_ring.play(self._scroll_sound)
			for li, line in enumerate(self._text_lines):
				line.target_y = li - i
		else:
			self._text_lines[i].opacity = 153

	def _on_confirm(self, i: int, selected: bool) -> None:
		if selected:
			self.game.set_scene(self.displayed_songs[i], DIFFICULTY.HARD, FreeplayScene)
