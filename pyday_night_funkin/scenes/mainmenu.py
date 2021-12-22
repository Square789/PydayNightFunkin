
import typing as t

from loguru import logger

from pyday_night_funkin.asset_system import load_asset, ASSETS
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.menu import Menu
from pyday_night_funkin import scenes
from pyday_night_funkin.core.tweens import TWEEN_ATTR, out_quad

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class MainMenuScene(scenes.BaseScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scroll_sound = load_asset(ASSETS.SOUND.MENU_SCROLL)
		self.confirm_sound = load_asset(ASSETS.SOUND.MENU_CONFIRM)

		self.bg = self.create_sprite("bg", image=load_asset(ASSETS.IMG.MENU_BG))
		self.bg_magenta = self.create_sprite("bg_mag", image=load_asset(ASSETS.IMG.MENU_DESAT))

		for bg in (self.bg, self.bg_magenta):
			bg.scroll_factor = (0.0, 0.18)
			bg.scale = 1.1
			bg.screen_center(CNST.GAME_DIMENSIONS)

		self.bg_magenta.visible = False
		self.bg_magenta.color = (0xFD, 0x71, 0x9B)

		menu_item_assets = load_asset(ASSETS.XML.MAIN_MENU_ASSETS)
		self._menu_items: t.List[t.Tuple[str, t.Callable[[], t.Any], "PNFSprite"]] = []
		for i, (name, callback) in enumerate((
			("story mode", self._sel_story_mode),
			("freeplay", self._sel_freeplay),
			("options", self._sel_options),
		)):
			sprite = self.create_sprite("fg", y=60 + i*160)
			sprite.animation.add_from_frames(
				"idle", menu_item_assets[f"{name} basic"], 24, True
			)
			sprite.animation.add_from_frames(
				"selected", menu_item_assets[f"{name} white"], 24, True
			)
			sprite.animation.play("idle", True)
			sprite.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self._menu_items.append((name, callback, sprite))

		self.menu = Menu(
			self.game.key_handler, len(self._menu_items), self._on_select, self._on_confirm
		)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "bg_mag", "fg")

	def _on_select(self, i: int, state: bool) -> None:
		s = self._menu_items[i][2]
		s.animation.play("selected" if state else "idle", True)
		s.check_animation_controller()
		s.screen_center(CNST.GAME_DIMENSIONS, y=False)
		if state:
			self._default_camera.set_follow_target(s.get_midpoint(), 0.06)

	def _on_confirm(self, i: int, selected: bool) -> None:
		_, callback, sprite = self._menu_items[i]
		if selected:
			sprite.start_flicker(1.0, 0.06, False, callback)

			self.sfx_ring.play(self.confirm_sound)
			self.bg_magenta.start_flicker(1.1, 0.15, False)
		else:
			sprite.start_tween(
				out_quad,
				{TWEEN_ATTR.OPACITY: 0},
				0.4,
				# I don't really have an equivalent to a FlxSpriteGroup's `kill`
				# Doesn't matter for this precise case anyways
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
