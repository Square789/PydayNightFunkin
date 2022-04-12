
import typing as t

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.core.pnf_text import ALIGNMENT, PNFText
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.tweens import TWEEN_ATTR, linear
from pyday_night_funkin.core.utils import dump_sprite_info, lerp, to_rgb_tuple, to_rgba_tuple
from pyday_night_funkin.enums import CONTROL, DIFFICULTY
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character
	from pyday_night_funkin.levels import Week


class _WeekHeader(PNFSprite):
	def __init__(self, target_y: int, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.target_y = target_y


class _WeekChar(PNFSprite):
	def __init__(self, initializing_char_type: t.Type["Character"], *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.displayed_char_type = initializing_char_type


class StoryMenuScene(scenes.MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.conductor.bpm = 102
		if not self.game.player.playing:
			self.game.player.set(load_asset(ASSET.MUSIC_MENU))

		yellow_stripe = self.create_object("mid", x=0, y=56)
		yellow_stripe.make_rect(to_rgba_tuple(0xF9CF51FF), CNST.GAME_WIDTH, 400)

		_story_menu_char_anims = load_asset(ASSET.XML_STORY_MENU_CHARACTERS)

		# Week character setup (these get modified later)
		self.week_chars: t.List[_WeekChar] = []
		for i in range(3):
			ty = WEEKS[0].story_menu_chars[i]
			spr = self.create_object(
				"fg",
				object_class = _WeekChar,
				initializing_char_type = None if ty is WEEKS[0].story_menu_chars[0] else ty,
				x = (CNST.GAME_WIDTH * 0.25 * (i + 1)) - 150 - (80 * (i == 1)),
				y = 70,
			)
			spr.frames = _story_menu_char_anims
			ty.initialize_story_menu_sprite(spr)
			spr.animation.play("story_menu")
			spr.scale = 0.9 if i == 1 else 0.5
			spr.recalculate_positioning()
			self.week_chars.append(spr)

		ui_tex = load_asset(ASSET.XML_STORY_MENU_UI)

		# Week headers
		self.week_headers: t.List[_WeekHeader] = []
		for i, week in enumerate(WEEKS):
			header = self.create_object(
				"bg",
				object_class = _WeekHeader,
				target_y = i,
				y = yellow_stripe.y + yellow_stripe.height + 10,
				image = load_asset(ASSET.WEEK_HEADERS, week.header_filename),
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

		load_asset(ASSET.FONT_VCR)
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
			self.game.key_handler, len(WEEKS), self._on_week_select, self._on_confirm
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
		return ("bg", "mid", "fg")

	def _on_week_select(self, index: int, state: bool) -> None:
		if not state:
			self.week_headers[index].opacity = 153
			return

		self.week_headers[index].opacity = 255
		self.sfx_ring.play(load_asset(ASSET.SOUND_MENU_SCROLL))
		for i, header in enumerate(self.week_headers):
			header.target_y = i - index

		self.week_title_txt.text = WEEKS[index].display_name
		self.week_title_txt.x = CNST.GAME_WIDTH - (self.week_title_txt.content_width + 10)

		self.tracklist_txt.text = "TRACKS\n\n" + "\n".join(
			scene.get_display_name().upper() for scene in WEEKS[index].levels
		)

		for i, week_char_display_sprite in enumerate(self.week_chars):
			target_char_type = WEEKS[index].story_menu_chars[i]
			if week_char_display_sprite.displayed_char_type is target_char_type:
				continue

			week_char_display_sprite.animation.remove("story_menu")
			if week_char_display_sprite.animation.exists("story_menu_confirm"):
				week_char_display_sprite.animation.remove("story_menu_confirm")
			target_char_type.initialize_story_menu_sprite(week_char_display_sprite)
			week_char_display_sprite.animation.play("story_menu")
			target_char_type.transform_story_menu_sprite(week_char_display_sprite)
			week_char_display_sprite.displayed_char_type = target_char_type

	def _on_diff_select(self, index: int, state: bool) -> None:
		if not state:
			return

		self.difficulty_indicator.animation.play(str(index))
		self.difficulty_indicator.y = self.diff_arrow_left.y - 15
		self.difficulty_indicator.opacity = 0
		self.difficulty_indicator.remove_effect()
		self.difficulty_indicator.start_tween(
			linear, {TWEEN_ATTR.Y: self.diff_arrow_left.y + 15, TWEEN_ATTR.OPACITY: 255}, 0.07
		)

	def _on_confirm(self, index: int, state: bool) -> None:
		if not state:
			return

		self.sfx_ring.play(load_asset(ASSET.SOUND_MENU_CONFIRM))
		self.week_chars[1].animation.play("story_menu_confirm")
		self.week_headers[index].start_toggle(
			1.0,
			0.1,
			on_toggle_on =  lambda s: setattr(s, "color", to_rgb_tuple(0x33FFFFFF)),
			on_toggle_off = lambda s: setattr(s, "color", to_rgb_tuple(CNST.WHITE)),
			on_complete =   lambda w=WEEKS[index]: self._set_ingame_scene(w),
		)

	def _set_ingame_scene(self, week: "Week") -> None:
		self.game.set_scene(
			week.levels[0],
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
		# NOTE: diff_menu can't ever see CONTROL.CONFIRM as pressed
		# since week_menu eats it up. Add a tiny hack here for that.
		if self.week_menu.choice_made:
			self.diff_menu.choice_made = True
		self.diff_menu.update()

		self.diff_arrow_left.animation.play("press" if kh[CONTROL.LEFT] else "idle")
		self.diff_arrow_right.animation.play("press" if kh[CONTROL.RIGHT] else "idle")
