
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin import characters as chars
from pyday_night_funkin.config import CONTROL
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin import scenes
from pyday_night_funkin.utils import create_pixel

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character


class WeekHeader(PNFSprite):
	"""
	Menu item that will force itself to a given y coordinate.
	"""

	def __init__(self, target_y: int, game_dims: t.Tuple[int, int], *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.target_y = target_y
		self.game_height = game_dims[1]


class StoryMenuScene(scenes.MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.conductor.bpm = 102

		self.add(TextLine("Under construction", bold=True, x=50, y=500))
		self.add(TextLine("Please leave", bold=True, x=50, y=570))

		self.mma = load_asset(ASSETS.XML.MAIN_MENU_ASSETS)

		yellow_stripe = self.create_sprite("bg", x=0, y=56, image=create_pixel(0xF9CF51FF))
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

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		kh = self.game.key_handler
		if kh.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.MainMenuScene)
