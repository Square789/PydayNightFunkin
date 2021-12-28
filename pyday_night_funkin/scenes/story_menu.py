
import typing as t

from pyday_night_funkin.asset_system import ASSET, load_asset
from pyday_night_funkin.config import CONTROL
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.pnf_label import PNFLabel
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.tweens import TWEEN_ATTR, linear
from pyday_night_funkin.enums import DIFFICULTY
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes
from pyday_night_funkin.utils import create_pixel, lerp, to_rgb_tuple

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character
	from pyday_night_funkin.levels import Week


# TODO this doesn't need to be its own class, just tear out the update
# calls and throw them into the main menu scene's
class _WeekHeader(PNFSprite):
	"""
	Menu item that will force itself to a given y coordinate.
	"""

	def __init__(self, target_y: int, game_dims: t.Tuple[int, int], *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.target_y = target_y
		self.game_height = game_dims[1]

	def update(self, dt: float) -> None:
		super().update(dt)
		self.y = lerp(self._y, (self.target_y * 120) + 480, 0.17)


class StoryMenuScene(scenes.MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.conductor.bpm = 102

		self._reverse_difficulty_map: t.List[DIFFICULTY] = [None] * len(DIFFICULTY)
		for diff in DIFFICULTY:
			self._reverse_difficulty_map[diff.value] = diff

		yellow_stripe = self.create_object("mid", x=0, y=56, image=CNST.PIXEL_TEXTURE)
		yellow_stripe.scale_x = CNST.GAME_WIDTH
		yellow_stripe.scale_y = 400
		yellow_stripe.color = to_rgb_tuple(0xF9CF51FF)

		# Week character setup (these get modified later)
		self.week_chars: t.List["Character"] = []
		for i in range(3):
			spr = self.create_object(
				"fg",
				object_class = WEEKS[0].story_menu_chars[i],
				scene = self,
				x = (CNST.GAME_WIDTH * 0.25 * (i + 1)) - 150,
				y = 70,
			)
			spr.animation.play("story_menu")
			(ox, oy), s = spr.get_story_menu_transform()
			spr.scale = s
			spr.x += ox
			spr.y += oy
			self.week_chars.append(spr)

		ui_tex = load_asset(ASSET.XML_STORY_MENU_UI)

		# Week headers
		self.week_headers: t.List[_WeekHeader] = []
		for i, week in enumerate(WEEKS):
			header = self.create_object(
				"bg",
				object_class = _WeekHeader,
				image = load_asset(ASSET.WEEK_HEADERS, week.header_filename),
				y = yellow_stripe.y + yellow_stripe.height + 10,
				target_y = i,
				game_dims = CNST.GAME_DIMENSIONS,
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
		self.diff_arrow_left.animation.add_from_frames("idle", ui_tex["arrow left"])
		self.diff_arrow_left.animation.add_from_frames("press", ui_tex["arrow push left"])
		self.diff_arrow_left.animation.play("idle")

		_diff_offset_map = {
			DIFFICULTY.EASY: (20, 0),
			DIFFICULTY.NORMAL: (70, 0),
			DIFFICULTY.HARD: (20, 0),
		}
		self.difficulty_indicator = self.create_object("bg", x=larrx + 130, y=larry)
		# Shoutouts to tyler "ninjamuffin99" blevins for using specific
		# animation frames for positioning of UI elements;
		# The fact that `EASY` is the first animation added is relevant here.
		for diff in DIFFICULTY:
			self.difficulty_indicator.animation.add_from_frames(
				str(diff.value), ui_tex[diff.to_atlas_prefix()], 24, True, _diff_offset_map[diff]
			)
		self.difficulty_indicator.animation.play("0")
		self.difficulty_indicator.check_animation_controller()

		self.diff_arrow_right = self.create_object(
			"bg",
			x=self.difficulty_indicator.x + self.difficulty_indicator.width + 50,
			y=larry,
		)
		self.diff_arrow_right.animation.add_from_frames("idle", ui_tex["arrow right"])
		self.diff_arrow_right.animation.add_from_frames("press", ui_tex["arrow push right"])
		self.diff_arrow_right.animation.play("idle")

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
		else:
			self.week_headers[index].opacity = 255
			self.sfx_ring.play(load_asset(ASSET.SOUND_MENU_SCROLL))
			for i, header in enumerate(self.week_headers):
				header.target_y = i - index

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
			1.0, 0.1, True, True,
			lambda s: setattr(s, "color", to_rgb_tuple(0x33FFFFFF)),
			lambda s: setattr(s, "color", to_rgb_tuple(CNST.WHITE)),
			lambda w=WEEKS[index]: self._set_ingame_scene(w),
		)

	def _set_ingame_scene(self, week: "Week") -> None:
		self.game.set_scene(
			week.levels[0],
			difficulty = self._reverse_difficulty_map[self.diff_menu.selection_index],
			follow_scene = StoryMenuScene,
			remaining_week = week.levels[1:],
		)

	def update(self, dt: float) -> None:
		super().update(dt)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)

		self.week_menu.update()
		# NOTE: diff_menu can't ever see CONTROL.CONFIRM as pressed
		# since week_menu eats it up. Add a tiny hack here for that.
		if self.week_menu.choice_made:
			self.diff_menu.choice_made = True
		self.diff_menu.update()
