
import typing as t

from pyday_night_funkin.alphabet import MenuTextLine
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.base_game_pack import fetch_character_icons
from pyday_night_funkin.core.asset_system import load_image, load_sound
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.pnf_text import TextAlignment, PNFText
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.enums import Control, Difficulty
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


class FreeplayScene(scenes.MusicBeatScene):
	def __init__(self, kernel) -> None:
		super().__init__(kernel.fill(layers=("bg", "fg", "textfg")))

		if not self.game.player.playing:
			self.game.player.set(load_sound("preload/music/freakyMenu.ogg"))

		self.bg = self.create_object("bg", image=load_image("preload/images/menuBGBlue.png"))

		self.score_text = self.create_object(
			"textfg",
			object_class = PNFText,
			x = CNST.GAME_WIDTH * .7,
			y = 5,
			font_name = "VCR OSD Mono",
			font_size = 32,
			color = to_rgba_tuple(CNST.WHITE),
			align = TextAlignment.RIGHT,
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

		self.displayed_songs = [lvl for week in self.game.weeks for lvl in week.levels]
		if not self.displayed_songs:
			raise RuntimeError("Panic at the FreeplayScene: No songs available!")

		self._cur_selection = 0
		self._scroll_sound = load_sound("preload/sounds/scrollMenu.ogg")
		self._text_lines: t.List[MenuTextLine] = []

		for i, lvl in enumerate(self.displayed_songs):
			m = MenuTextLine(
				i,
				CNST.GAME_DIMENSIONS,
				text = lvl.display_name,
				bold = True,
				x = 0,
				y = 70*i + 30,
			)
			m.opacity = 153
			self._text_lines.append(m)
			self.add(m, "fg")

			opp_icon = self.game.character_registry[lvl.opponent_character].icon_name
			self.create_object(
				"fg",
				object_class = StickySprite,
				stickee = m,
				image = fetch_character_icons(opp_icon)[0],
			)

		self.menu = Menu(
			self.game.key_handler, len(self.displayed_songs), self._on_select, self._on_confirm
		)
		self.diff_menu = Menu(
			self.game.key_handler,
			len(Difficulty),
			self._on_diff_select,
			ini_selection_index = 1,
			fwd_control = Control.RIGHT,
			bkwd_control = Control.LEFT,
		)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(Control.BACK):
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
				self.displayed_songs[i].stage_type.get_kernel(
					self.displayed_songs[i],
					Difficulty(self.diff_menu.selection_index),
					FreeplayScene,
				)
			)

	def _on_diff_select(self, i: int, state: bool) -> None:
		if state:
			self.diff_text.text = Difficulty(i).name
