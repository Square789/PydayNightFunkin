
import typing as t

from loguru import logger

from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.asset_system import load_frames, load_image, load_sound
from pyday_night_funkin.core.tween_effects.eases import out_quad
from pyday_night_funkin.core.utils import to_rgb_tuple
from pyday_night_funkin.enums import Control
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class MainMenuScene(scenes.MusicBeatScene):
	def __init__(self, kernel) -> None:
		super().__init__(kernel.fill(layers=("bg", "bg_mag", "fg")))

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

		menu_item_assets = load_frames("preload/images/main_menu.xml")
		self._menu_items: t.List[t.Tuple[str, t.Callable[[], t.Any], "PNFSprite"]] = []
		for i, (name, callback) in enumerate((
			("story mode", self._sel_story_mode),
			("freeplay", self._sel_freeplay),
			("options", self._sel_options),
		)):
			sprite = self.create_object("fg", y=60 + i*160)
			sprite.frames = menu_item_assets
			sprite.animation.add_by_prefix("idle", f"{name} idle", 24, True)
			sprite.animation.add_by_prefix("selected", f"{name} selected", 24, True)
			sprite.animation.play("idle", True)
			sprite.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self._menu_items.append((name, callback, sprite))

		self.menu = Menu(
			self.game.key_handler, len(self._menu_items), self._on_select, self._on_confirm
		)

	def _on_select(self, i: int, state: bool) -> None:
		s = self._menu_items[i][2]
		s.animation.play("selected" if state else "idle", True)
		s.recalculate_positioning()
		s.screen_center(CNST.GAME_DIMENSIONS, y=False)
		if state:
			self.sfx_ring.play(self.scroll_sound)
			self.default_camera.set_follow_target(s.get_midpoint(), 0.06)

	def _on_confirm(self, i: int, selected: bool) -> None:
		_, callback, sprite = self._menu_items[i]
		if selected:
			self.sfx_ring.play(self.confirm_sound)
			self.effects.flicker(sprite, 1.0, 0.06, False, lambda _, c=callback: c())
			self.effects.flicker(self.bg_magenta, 1.1, 0.15, False)
		else:
			self.effects.tween(
				sprite,
				{"opacity": 0},
				0.4,
				out_quad,
				lambda s: setattr(s, "visible", False),
			)

	def update(self, dt: float) -> None:
		super().update(dt)
		if self.menu.choice_made:
			return

		if self.game.key_handler.just_pressed(Control.BACK):
			self.game.set_scene(scenes.TitleScene)
			return

		self.menu.update()

	def _sel_story_mode(self) -> None:
		self.game.set_scene(scenes.StoryMenuScene)

	def _sel_freeplay(self) -> None:
		self.game.set_scene(scenes.FreeplayScene)

	def _sel_options(self) -> None:
		self.game.set_scene(scenes.SettingsScene)
