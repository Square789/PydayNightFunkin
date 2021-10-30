
import typing as t

from loguru import logger

from pyday_night_funkin.asset_system import load_asset, ASSETS
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.enums import DIFFICULTY
from pyday_night_funkin.scenes.music_beat import MusicBeatScene
from pyday_night_funkin.tweens import TWEEN_ATTR, out_quad

if t.TYPE_CHECKING:
	from pyday_night_funkin.graphics import PNFSprite


TitleScene = None
def _cyclic_import_break():
	global TitleScene
	from pyday_night_funkin.scenes.title import TitleScene


class MainMenuScene(MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.conductor.bpm = 102

		_cyclic_import_break()

		self._menu_items = [
			["story mode", self._sel_story_mode, None],
			["freeplay", self._sel_freeplay, None],
			["options", self._sel_options, None],
		]

		self.selected_idx = 0

		self.selection_confirmed = False

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
		for i, list_ in enumerate(self._menu_items):
			name = list_[0]
			sprite = self.create_sprite("fg", y = 60 + i*160)
			sprite.animation.add_from_frames("idle", menu_item_assets[f"{name} basic"])
			sprite.animation.add_from_frames("selected", menu_item_assets[f"{name} white"])
			sprite.animation.play("idle")
			sprite.screen_center(CNST.GAME_DIMENSIONS, y=False)
			list_[2] = sprite

		self.change_item(0)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "bg_mag", "fg")

	def change_item(self, by: int) -> None:
		self.selected_idx += by
		self.selected_idx %= len(self._menu_items)

		for i, (_, _, sprite) in enumerate(self._menu_items):
			if i == self.selected_idx:
				sprite.animation.play("selected")
				self._default_camera.set_follow_target(sprite.get_midpoint(), 0.06)
			else:
				sprite.animation.play("idle")

	def update(self, dt: float) -> None:
		super().update(dt)

		if not self.selection_confirmed:
			kh = self.game.key_handler

			if kh.just_pressed(CONTROL.UP):
				self.sfx_ring.play(self.scroll_sound)
				self.change_item(-1)

			if kh.just_pressed(CONTROL.DOWN):
				self.sfx_ring.play(self.scroll_sound)
				self.change_item(1)

			if kh.just_pressed(CONTROL.BACKSPACE):
				self.game.set_scene(TitleScene)

			if kh.just_pressed(CONTROL.ENTER):
				self.selection_confirmed = True
				self.sfx_ring.play(self.confirm_sound)

				self.bg_magenta.start_flicker(1.1, 0.15, False)

				for i, (name, callback, sprite) in enumerate(self._menu_items):
					if i != self.selected_idx:
						sprite.start_tween(
							out_quad,
							{TWEEN_ATTR.OPACITY: 0},
							0.4,
							# I don't really have an equivalent to a FlxSpriteGroup's `kill`
							# Doesn't matter for this precise case anyways
							lambda sprite=sprite: setattr(sprite, "visible", False),
						)
					else:
						sprite.start_flicker(1.0, 0.06, False, callback)
						# callback()

		for _, _, sprite in self._menu_items:
			sprite.screen_center(CNST.GAME_DIMENSIONS, y=False)

	def _sel_story_mode(self) -> None:
		# may god smite you, o cursed circular imports!
		from pyday_night_funkin.levels import WEEKS

		self.game.set_scene(WEEKS[1].levels[1], DIFFICULTY.HARD, type(self))

	def _sel_freeplay(self) -> None:
		logger.info("Sorry nothing")
		self.game.set_scene(TitleScene)

	def _sel_options(self) -> None:
		logger.info("No options yet")
		self.game.set_scene(TitleScene)