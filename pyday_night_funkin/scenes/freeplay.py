
import typing as t

from pyday_night_funkin.alphabet import MenuTextLine
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.asset_system import load_asset, ASSET
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.pnf_text import ALIGNMENT, PNFText
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.enums import CONTROL, DIFFICULTY
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes


class StickySprite(PNFSprite):
	def __init__(self, stickee: PNFSprite, *args, **kwargs) -> None:
		self.stickee = stickee
		super().__init__(*args, **kwargs)

	def update(self, dt: float) -> None:
		super().update(dt)
		self.x = self.stickee.x + self.stickee.width + 10
		self.y = self.stickee.y - 30


class FreeplayScene(BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		from pyday_night_funkin.levels import WEEKS

		super().__init__(*args, **kwargs)

		if not self.game.player.playing:
			self.game.player.set(load_asset(ASSET.MUSIC_MENU))

		self.bg = self.create_object("bg", image=load_asset(ASSET.IMG_MENU_BG_BLUE))

		load_asset(ASSET.FONT_VCR)
		self.score_text = self.create_object(
			"textfg",
			object_class = PNFText,
			x = CNST.GAME_WIDTH * .7,
			y = 5,
			font_name = "VCR OSD Mono",
			font_size = 32,
			color = to_rgba_tuple(CNST.WHITE),
			align = ALIGNMENT.RIGHT,
		)
		self.diff_text = self.create_object(
			"textfg",
			object_class = PNFText,
			x = self.score_text.x,
			y = self.score_text.y + 36,
			font_name = "VCR OSD Mono",
			font_size = 24,
		)

		score_bg = self.create_object("fg", x=self.score_text.x - 6, y=0)
		score_bg.make_rect(to_rgba_tuple(CNST.BLACK), CNST.GAME_WIDTH * .35, 66)
		score_bg.opacity = 153

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
			self.create_object(
				"fg",
				object_class = StickySprite,
				stickee = m,
				image = load_asset(ASSET.IMG_ICON_GRID, lvl.get_opponent_icon())[0],
			)
			# NOTE: should probably call `lvl.get_opponent().icon_name` or something,
			# but creating opponent without an in game scene sorta sucks.
			# This is a crappy leftover, try to get rid of it some time (TM)

		self.menu = Menu(
			self.game.key_handler, len(self.displayed_songs), self._on_select, self._on_confirm
		)
		self.diff_menu = Menu(
			self.game.key_handler,
			len(DIFFICULTY),
			self._on_diff_select,
			ini_selection_index = 1,
			fwd_control = CONTROL.RIGHT,
			bkwd_control = CONTROL.LEFT,
		)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg", "textfg")

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)
			return # Don't want any menu callbacks to trigger when this block runs

		self.menu.update()
		if self.menu.choice_made:
			self.diff_menu.choice_made = True
		self.diff_menu.update()

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
			self.game.set_scene(
				self.displayed_songs[i],
				DIFFICULTY(self.diff_menu.selection_index),
				FreeplayScene,
			)

	def _on_diff_select(self, i: int, state: bool) -> None:
		if state:
			self.diff_text.text = DIFFICULTY(i).name

