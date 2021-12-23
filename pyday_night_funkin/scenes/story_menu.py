
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.config import CONTROL
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.enums import DIFFICULTY
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin import scenes
from pyday_night_funkin.menu import Menu
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

		yellow_stripe = self.create_sprite("mid", x=0, y=56, image=create_pixel(0xF9CF51FF))
		yellow_stripe.scale_x = CNST.GAME_WIDTH
		yellow_stripe.scale_y = 400

		self._current_week = 0

		self.week_chars: t.List["Character"] = []
		for i in range(3):
			spr = self.create_sprite(
				"fg",
				sprite_class = WEEKS[self._current_week].story_menu_chars[i],
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

		ui_tex = load_asset(ASSETS.XML.STORY_MENU_UI)

		self.difficulty_indicator = self.create_sprite("bg")
		for diff in DIFFICULTY:
			self.difficulty_indicator.animation.add_from_frames(
				str(diff.value), ui_tex[diff.to_atlas_prefix()], 24, True
			)

		self.week_headers: t.List["_WeekHeader"] = []
		for i, week in enumerate(WEEKS):
			header = self.create_sprite(
				"bg",
				sprite_class = _WeekHeader,
				y = yellow_stripe.y + yellow_stripe.height + 10,
				target_y = i,
				game_dims = CNST.GAME_DIMENSIONS,
			)
			header.y += (header.height + 20) * i
			header.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self.week_headers.append(header)
			# TODO Images
			# TODO Locks

		self.week_menu = Menu(
			self.game.key_handler, len(WEEKS), self._on_week_select, self._on_confirm
		)
		self.diff_menu = Menu(
			self.game.key_handler,
			len(DIFFICULTY),
			self._on_diff_select,
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
			self.sfx_ring.play(load_asset(ASSETS.SOUND.MENU_SCROLL))
			for i, header in enumerate(self.week_headers):
				header.target_y = i - index

	def _on_diff_select(self, index: int, state: bool) -> None:
		if not state:
			return

		self.difficulty_indicator.animation.play(str(index))

	def _on_confirm(self, index: int, state: bool) -> None:
		if not state:
			return

		self.sfx_ring.play(load_asset(ASSETS.SOUND.MENU_CONFIRM))
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
			created_from = StoryMenuScene,
		)

	def update(self, dt: float) -> None:
		super().update(dt)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)

		self.week_menu.update()
		# NOTE: Only the week menu triggers on_confirm.
		# diff_menu can't ever see CONTROL.CONFIRM as pressed
		# since week_menu eats it up. Add a tiny hack here for that.
		if self.week_menu.choice_made:
			self.diff_menu.choice_made = True
		self.diff_menu.update()
