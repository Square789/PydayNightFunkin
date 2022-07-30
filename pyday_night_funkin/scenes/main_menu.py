
import typing as t

from loguru import logger

from pyday_night_funkin import constants as CNST
from pyday_night_funkin.base_game_pack import load_frames
from pyday_night_funkin.core.asset_system import load_image, load_sound
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.core.tweens import TWEEN_ATTR, out_quad
from pyday_night_funkin.core.utils import to_rgb_tuple
from pyday_night_funkin.enums import CONTROL
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class MainMenuScene(BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scroll_sound = load_sound("preload/sounds/scrollMenu.ogg")
		self.confirm_sound = load_sound("preload/sounds/confirmMenu.ogg")

		self.bg = self.create_object("bg", image=load_image("preload/images/menuBG.png"))
		self.bg_magenta = self.create_object(
			"bg_mag", image=load_image("preload/images/menuDesat.png")
		)

		for bg in (self.bg, self.bg_magenta):
			bg.scroll_factor = (0.0, 0.18)
			bg.set_scale_and_repos(1.1)
			bg.screen_center(CNST.GAME_DIMENSIONS)

		self.bg_magenta.visible = False
		self.bg_magenta.color = to_rgb_tuple(0xFD719BFF)

		menu_item_assets = load_frames("preload/images/FNF_main_menu_assets.xml")
		self._menu_items: t.List[t.Tuple[str, t.Callable[[], t.Any], "PNFSprite"]] = []
		for i, (name, callback) in enumerate((
			("story mode", self._sel_story_mode),
			("freeplay", self._sel_freeplay),
			("options", self._sel_options),
		)):
			sprite = self.create_object("fg", y=60 + i*160)
			sprite.frames = menu_item_assets
			sprite.animation.add_by_prefix("idle", f"{name} basic", 24, True)
			sprite.animation.add_by_prefix("selected", f"{name} white", 24, True)
			sprite.animation.play("idle", True)
			sprite.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self._menu_items.append((name, callback, sprite))

		self.menu = Menu(
			self.game.key_handler, len(self._menu_items), self._on_select, self._on_confirm
		)

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "bg_mag", "fg")

	def _on_select(self, i: int, state: bool) -> None:
		s = self._menu_items[i][2]
		s.animation.play("selected" if state else "idle", True)
		s.recalculate_positioning()
		s.screen_center(CNST.GAME_DIMENSIONS, y=False)
		if state:
			self.sfx_ring.play(self.scroll_sound)
			self._default_camera.set_follow_target(s.get_midpoint(), 0.06)

	def _on_confirm(self, i: int, selected: bool) -> None:
		_, callback, sprite = self._menu_items[i]
		if selected:
			self.sfx_ring.play(self.confirm_sound)
			sprite.start_flicker(1.0, 0.06, False, callback)
			self.bg_magenta.start_flicker(1.1, 0.15, False)
		else:
			sprite.start_tween(
				out_quad,
				{TWEEN_ATTR.OPACITY: 0},
				0.4,
				lambda sprite=sprite: setattr(sprite, "visible", False),
			)

	def update(self, dt: float) -> None:
		super().update(dt)
		if self.menu.choice_made:
			return

		if self.game.key_handler.just_pressed(CONTROL.BACK):
			self.game.set_scene(scenes.TitleScene)
			return

		self.menu.update()

	def _sel_story_mode(self) -> None:
		self.game.set_scene(scenes.StoryMenuScene)

	def _sel_freeplay(self) -> None:
		self.game.set_scene(scenes.FreeplayScene)

	def _sel_options(self) -> None:
		logger.info("No options yet")
		self.game.set_scene(scenes.TitleScene)
