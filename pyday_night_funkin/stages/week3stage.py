
from random import randint
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.constants import GAME_WIDTH
from pyday_night_funkin.core.asset_system import load_image, load_sound
from pyday_night_funkin.core.scene import OrderedLayer
from pyday_night_funkin.stages.common import BaseGameBaseStage
from pyday_night_funkin.scenes.in_game import CharacterAnchor, InGameSceneKernel

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class Week3Stage(BaseGameBaseStage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				layers = (
					"sky", "city", "lights", OrderedLayer("train"), "girlfriend", "stage",
					OrderedLayer("ui_combo"), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
				),
				default_cam_zoom = 1.05,
				opponent_anchor = CharacterAnchor(Vec2(100, 400), None, "stage"),
			),
			*args,
			**kwargs,
		)

		self.city_lights: t.List[PNFSprite] = []
		self._active_city_light_idx: int = 0
		self.train_sound = load_sound("shared/sounds/train_passes.ogg")
		self.train_inbound = False
		self.train_moving = False
		self.train_cars_remaining = 8
		self.train_timer = 0.0
		self.train_cooldown = -4

		# Fuck if i know, make a player specifically for this sound because there
		# are things that depend on ITS AUDIO POSITION ARRGGHHG
		# TODO: should probably look into a workaround that is pretty much identical
		# yet 500% less crappy
		self.train_sound_player = self.game.sound.create_player()

		bg = self.create_object(
			"sky", "main", x=-100, image=load_image("week3/images/philly/sky.png")
		)
		bg.scroll_factor = (.1, .1)

		city = self.create_object(
			"city", "main", x=-10, image=load_image("week3/images/philly/city.png")
		)
		city.scroll_factor = (.3, .3)
		city.set_scale_and_repos(.85)

		for i in range(5):
			light = self.create_object(
				"lights", "main", x=city.x, image=load_image(f"week3/images/philly/win{i}.png")
			)
			light.scroll_factor = (.3, .3)
			light.visible = False
			light.set_scale_and_repos(.85)
			self.city_lights.append(light)

		sokagrafie = self.create_object(
			"train", "main", x=-40, y=50, image=load_image("week3/images/philly/behindTrain.png")
		)
		self.train = self.create_object(
			"train", "main", x=2000, y=360, image=load_image("week3/images/philly/train.png")
		)
		self.create_object(
			"train", "main",
			x=-40, y=sokagrafie.y, image=load_image("week3/images/philly/street.png")
		)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.train_inbound:
			self.train_timer += dt
			if self.train_timer >= 1/24:
				self._update_train()

	def _update_train(self) -> None:
		self.train_timer = .0
		if not self.train_moving:
			if self.train_sound_player.time <= 4.7:
				return
			self.train_moving = True
			self.girlfriend.animation.play("hair_blow")

		self.train.x -= 400
		if self.train.x < -2000 and self.train_cars_remaining > 0:
			self.train.x = -1150
			self.train_cars_remaining -= 1
		if self.train.x < -4000 and self.train_cars_remaining <= 0:
			self.girlfriend.animation.play("hair_fall")
			self.train.x = GAME_WIDTH + 200
			self.train_inbound = self.train_moving = False
			self.train_cars_remaining = 8

	def on_pause(self) -> None:
		super().on_pause()
		self.train_sound_player.pause()

	def on_subscene_removal(self, *a, **kw) -> None:
		super().on_subscene_removal(*a, **kw)
		self.train_sound_player.play()

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if self.cur_beat % 4 == 0:
			self.city_lights[self._active_city_light_idx].visible = False
			self._active_city_light_idx = randint(0, len(self.city_lights) - 1)
			self.city_lights[self._active_city_light_idx].visible = True

		if self.train_inbound:
			return

		self.train_cooldown += 1
		# cooldown > 8 by original game but make it juust a bit less frequent
		if self.cur_beat % 8 == 4 and randint(0, 99) < 30 and self.train_cooldown > 10:
			self.train_cooldown = randint(-4, 0)
			self.train_inbound = True
			# if not self.train_sound_player.playing:
			self.train_sound_player.set(self.train_sound)

	def destroy(self) -> None:
		super().destroy()
		self.train_sound_player.delete()
