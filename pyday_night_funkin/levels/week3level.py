
from random import choice, randint
import typing as t

from pyday_night_funkin.base_game_pack import Boyfriend, Girlfriend, Pico as PicoChar
from pyday_night_funkin.constants import GAME_WIDTH
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.core.pnf_player import PNFPlayer
from pyday_night_funkin.scenes import InGameScene
from pyday_night_funkin.levels import common

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.hud import HUD
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class Week3Level(InGameScene):
	def __init__(self, *args, **kwargs) -> None:
		self.city_lights: t.List[PNFSprite] = []
		self._active_city_light_idx: int = 0
		self.train: t.Optional[PNFSprite] = None
		self.train_sound = load_asset(ASSET.SOUND_TRAIN)
		# Fuck if i know, make a player specifically for this sound because there
		# are things that depend on ITS AUDIO POSITION ARRGGHHG
		# TODO: should probably look into a workaround that is pretty much identical
		# yet 500% less crappy
		self.train_sound_player = PNFPlayer()
		self.train_inbound = False
		self.train_moving = False
		self.train_cars_remaining = 8
		self.train_timer = 0.0
		self.train_cooldown = -4

		super().__init__(*args, **kwargs)

	@staticmethod
	def get_opponent_icon() -> str:
		return "pico"

	def create_note_handler(self) -> "AbstractNoteHandler":
		return common.create_note_handler(self)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (
			"sky", "city", "lights", ("train", True), "girlfriend", "stage",
			("ui_combo", True), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
		)

	def create_hud(self) -> "HUD":
		return common.create_hud(self)

	def setup(self) -> None:
		super().setup()
		bg = self.create_object("sky", "main", x=-100, image=load_asset(ASSET.IMG_PHILLY_SKY))
		bg.scroll_factor = (.1, .1)

		city = self.create_object("city", "main", x=-10, image=load_asset(ASSET.IMG_PHILLY_CITY))
		city.scroll_factor = (.3, .3)
		city.set_scale_and_repos(.85)

		for i in range(5):
			light = self.create_object(
				"lights", "main", x=city.x, image=load_asset(getattr(ASSET, f"IMG_PHILLY_WIN{i}"))
			)
			light.scroll_factor = (.3, .3)
			light.visible = False
			light.set_scale_and_repos(.85)
			self.city_lights.append(light)

		sokagrafie = self.create_object(
			"train", "main", x=-40, y=50, image=load_asset(ASSET.IMG_PHILLY_BEHIND_TRAIN)
		)
		self.train = self.create_object(
			"train", "main", x=2000, y=360, image=load_asset(ASSET.IMG_PHILLY_TRAIN)
		)
		self.create_object(
			"train", "main", x=-40, y=sokagrafie.y, image=load_asset(ASSET.IMG_PHILLY_STREET)
		)

	def create_boyfriend(self) -> "Boyfriend":
		return self.create_object("stage", "main", Boyfriend, scene=self, x=770, y=450)

	def create_girlfriend(self) -> "Girlfriend":
		gf = self.create_object("girlfriend", "main", Girlfriend, scene=self, x=400, y=130)
		gf.scroll_factor = (.95, .95)
		return gf

	def create_opponent(self) -> "Character":
		return self.create_object("stage", "main", PicoChar, scene=self, x=100, y=400)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.train_inbound:
			self.train_timer += dt
			if self.train_timer >= 1/24:
				self._update_train()

	def _update_train(self) -> None:
		self.train_timer = .0
		if not self.train_moving and self.train_sound_player.time > 4.7:
			self.train_moving = True
			self.girlfriend.animation.play("hair_blow")
		if self.train_moving:
			self.train.x -= 400
			if self.train.x < -2000 and self.train_cars_remaining > 0:
				self.train.x = -1150
				self.train_cars_remaining -= 1
			if self.train.x < -4000 and self.train_cars_remaining <= 0:
				self.girlfriend.animation.play("hair_fall")
				self.train.x = GAME_WIDTH + 200
				self.train_inbound = self.train_moving = False
				self.train_cars_remaining = 8

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if self.cur_beat % 4 == 0:
			self.city_lights[self._active_city_light_idx].visible = False
			self._active_city_light_idx = randint(0, len(self.city_lights) - 1)
			self.city_lights[self._active_city_light_idx].visible = True

		if self.train_inbound:
			return

		self.train_cooldown += 1
		if self.cur_beat % 8 == 4 and randint(0, 99) < 30 and self.train_cooldown > 8:
			self.train_cooldown = randint(-4, 0)
			self.train_inbound = True
			if not self.train_sound_player.playing:
				self.train_sound_player.set(self.train_sound)

	def delete(self) -> None:
		super().delete()
		self.train_sound_player.delete()


class Pico(Week3Level):
	@staticmethod
	def get_song() -> str:
		return "pico"

class Philly(Week3Level):
	@staticmethod
	def get_song() -> str:
		return "philly"

class Blammed(Week3Level):
	@staticmethod
	def get_song() -> str:
		return "blammed"
