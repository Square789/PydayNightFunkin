
import typing as t

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.base_game_pack import load_frames, load_week_header
from pyday_night_funkin.core.asset_system import load_sound
from pyday_night_funkin.core.pnf_text import ALIGNMENT, PNFText
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.tweens import linear
from pyday_night_funkin.core.utils import lerp, to_rgb_tuple, to_rgba_tuple
from pyday_night_funkin.enums import CONTROL, DIFFICULTY
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character
	from pyday_night_funkin.content_pack import WeekData


class _WeekHeader(PNFSprite):
	def __init__(self, target_y: int, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.target_y = target_y


class _WeekChar(PNFSprite):
	def __init__(self, displayed_char: t.Hashable, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.displayed_char = displayed_char

	def display_new_char(self, char_id: t.Hashable, char_cls: t.Type["Character"]) -> None:
		if self.displayed_char == char_id:
			return

		self.animation.remove("story_menu")
		if self.animation.exists("story_menu_confirm"):
			self.animation.remove("story_menu_confirm")

		char_cls.initialize_story_menu_sprite(self)
		self.animation.play("story_menu")
		# 214.5 is extracted as the default `width` of sprite 0, which is truth is kind of
		# a constant as Daddy Dearest will always be the character the story menu is created with.
		self.scale = 214.5 / self.get_current_frame_dimensions()[0]
		self.offset = char_cls.get_character_data().story_menu_offset
		self.displayed_char = char_id


class StoryMenuScene(scenes.MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self._weeks = self.game.weeks # same list, who cares, we're only reading it.
		if not self._weeks:
			raise RuntimeError("No weeks available!")

		self.conductor.bpm = 102
		if not self.game.player.playing:
			self.game.player.set(load_sound("preload/music/freakyMenu.ogg"))

		yellow_stripe = self.create_object("mid", x=0, y=56)
		yellow_stripe.make_rect(to_rgba_tuple(0xF9CF51FF), CNST.GAME_WIDTH, 400)

		_story_menu_char_anims = load_frames("preload/images/campaign_menu_UI_characters.xml")

		# Week character setup (these get modified later)
		self.week_chars: t.List[_WeekChar] = []
		for i in range(3):
			char_id = self._weeks[0].story_menu_chars[i]
			char_type = self.game.character_registry[char_id]
			spr = self.create_object(
				"fg",
				object_class = _WeekChar,
				displayed_char = None if char_id == self._weeks[0].story_menu_chars[0] else char_id,
				x = (CNST.GAME_WIDTH * 0.25 * (i + 1)) - 150 - (80 * (i == 1)),
				y = 70,
			)
			spr.frames = _story_menu_char_anims
			char_type.initialize_story_menu_sprite(spr)
			spr.animation.play("story_menu")
			spr.scale = 0.9 if i == 1 else 0.5
			spr.recalculate_positioning()
			self.week_chars.append(spr)

		ui_tex = load_frames("preload/images/campaign_menu_UI_assets.xml")

		# Week headers
		self.week_headers: t.List[_WeekHeader] = []
		for i, week in enumerate(self._weeks):
			header = self.create_object(
				"bg",
				object_class = _WeekHeader,
				target_y = i,
				y = yellow_stripe.y + yellow_stripe.height + 10,
				image = load_week_header(week.header_filename),
			)
			header.y += (header.height + 20) * i
			header.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self.week_headers.append(header)
			# TODO Images
			# TODO Locks

		# Difficulty selectors
		larrx = self.week_headers[0].x + self.week_headers[0].width + 10
		larry = self.week_headers[0].y + 10

		self.diff_arrow_left = self.create_object("bg", x=larrx, y=larry)
		self.diff_arrow_left.frames = ui_tex
		self.diff_arrow_left.animation.add_by_prefix("idle", "arrow left")
		self.diff_arrow_left.animation.add_by_prefix("press", "arrow push left")
		self.diff_arrow_left.animation.play("idle")

		_diff_offset_map = {
			DIFFICULTY.EASY: (20, 0),
			DIFFICULTY.NORMAL: (70, 0),
			DIFFICULTY.HARD: (20, 0),
		}
		self.difficulty_indicator = self.create_object("bg", x=larrx + 130, y=larry)
		self.difficulty_indicator.frames = ui_tex
		for diff in DIFFICULTY:
			self.difficulty_indicator.animation.add_by_prefix(
				str(diff.value), diff.to_atlas_prefix(), offset=_diff_offset_map[diff]
			)
		self.difficulty_indicator.animation.play("0")

		self.diff_arrow_right = self.create_object(
			"bg",
			x=self.difficulty_indicator.x + self.difficulty_indicator.width + 50,
			y=larry,
		)
		self.diff_arrow_right.frames = ui_tex
		self.diff_arrow_right.animation.add_by_prefix("idle", "arrow right")
		self.diff_arrow_right.animation.add_by_prefix("press", "arrow push right")
		self.diff_arrow_right.animation.play("idle")

		self.tracklist_txt = self.create_object(
			"bg",
			object_class = PNFText,
			x = (CNST.GAME_WIDTH - 500) * .5 - CNST.GAME_WIDTH * .35,
			y = yellow_stripe.height + 100,
			text = "TRACKS",
			font_name = "VCR OSD Mono",
			font_size = 32,
			color = to_rgba_tuple(0xE55777FF),
			multiline = True,
			align = ALIGNMENT.CENTER,
			width = 500,
		)
		self.week_title_txt = self.create_object(
			"bg",
			object_class = PNFText,
			x = CNST.GAME_WIDTH * 0.7,
			y = 10,
			text = "",
			font_name = "VCR OSD Mono",
			font_size = 32,
			color = to_rgba_tuple(0xFFFFFFB3),
		)

		# Menus
		self.week_menu = Menu(
			self.game.key_handler, len(self._weeks), self._on_week_select, self._on_confirm
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
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "mid", "fg")

	def _on_week_select(self, index: int, state: bool) -> None:
		if not state:
			self.week_headers[index].opacity = 153
			return

		self.week_headers[index].opacity = 255
		self.sfx_ring.play(load_sound("preload/sounds/scrollMenu.ogg"))
		for i, header in enumerate(self.week_headers):
			header.target_y = i - index

		self.week_title_txt.text = self._weeks[index].display_name
		self.week_title_txt.x = CNST.GAME_WIDTH - (self.week_title_txt.content_width + 10)

		self.tracklist_txt.text = "TRACKS\n\n" + "\n".join(
			level.display_name.upper() for level in self._weeks[index].levels
		)

		for i, week_char_display_sprite in enumerate(self.week_chars):
			new_char_id = self._weeks[index].story_menu_chars[i]
			new_char_type = self.game.character_registry[new_char_id]
			week_char_display_sprite.display_new_char(new_char_id, new_char_type)

	def _on_diff_select(self, index: int, state: bool) -> None:
		if not state:
			return

		self.difficulty_indicator.animation.play(str(index))
		self.difficulty_indicator.y = self.diff_arrow_left.y - 15
		self.difficulty_indicator.opacity = 0
		self.difficulty_indicator.remove_effect()
		self.difficulty_indicator.start_tween(
			linear, {"y": self.diff_arrow_left.y + 15, "opacity": 255}, 0.07
		)

	def _on_confirm(self, index: int, state: bool) -> None:
		if not state:
			return

		self.sfx_ring.play(load_sound("preload/sounds/confirmMenu.ogg"))
		self.week_chars[1].animation.play("story_menu_confirm")
		self.week_headers[index].start_toggle(
			1.0,
			0.1,
			on_toggle_on =  lambda s: setattr(s, "color", to_rgb_tuple(0x33FFFFFF)),
			on_toggle_off = lambda s: setattr(s, "color", to_rgb_tuple(CNST.WHITE)),
			on_complete =   lambda w=self._weeks[index]: self._set_ingame_scene(w),
		)

	def _set_ingame_scene(self, week: "WeekData") -> None:
		level = week.levels[0]
		self.game.set_scene(
			level.stage_class,
			level_data = level,
			difficulty = DIFFICULTY(self.diff_menu.selection_index),
			follow_scene = StoryMenuScene,
			remaining_week = week.levels[1:],
		)

	def update(self, dt: float) -> None:
		super().update(dt)

		for wh in self.week_headers:
			wh.y = lerp(wh.y, (wh.target_y * 120) + 480, .17)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)

		self.week_menu.update()
		self.diff_menu.update()

		self.diff_arrow_left.animation.play("press" if kh[CONTROL.LEFT] else "idle")
		self.diff_arrow_right.animation.play("press" if kh[CONTROL.RIGHT] else "idle")
