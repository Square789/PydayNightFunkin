
from random import choice, randint
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.base_game_pack import load_frames
from pyday_night_funkin.core.asset_system import load_image, load_sound
from pyday_night_funkin.core.scene import OrderedLayer
from pyday_night_funkin.stages.common import BaseGameBaseStage
from pyday_night_funkin.scenes.in_game import CharacterAnchor, InGameSceneKernel

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import CharacterData
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class Week4Stage(BaseGameBaseStage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				layers = (
					"sky", "limo_bg", "henchmen", "girlfriend", "limo", "stage", "car",
					OrderedLayer("ui_combo"), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
				),
				default_cam_zoom = 0.9,
				player_anchor = CharacterAnchor(Vec2(1030, 230), None, "stage"),
			),
			*args,
			**kwargs,
		)

		self._henchmen: t.List[PNFSprite] = []
		self._henchmen_next_right = True
		self._allow_passing_car = False
		self._car_sounds = [load_sound(f"shared/sounds/carPass{i}.ogg") for i in range(2)]

		sky = self.create_object(
			"sky", x=-120, y=-50, image=load_image("week4/images/limo/limoSunset.png")
		)
		sky.scroll_factor = (0.1, 0.1)

		bg_limo = self.create_object("limo_bg", x=-200, y=480)
		bg_limo.scroll_factor = (0.4, 0.4)
		bg_limo.frames = load_frames("week4/images/limo/bgLimo.xml")
		bg_limo.animation.add_by_prefix("drive", "background limo pink")
		bg_limo.animation.play("drive")

		for i in range(4):
			chad = self.create_object("henchmen", x=(370*i) + 130, y=bg_limo.y - 400)
			chad.scroll_factor = (0.4, 0.4)
			chad.frames = load_frames("week4/images/limo/limoDancer.xml")
			chad.animation.add_by_indices(
				"dance_left", "bg dancer sketch PINK", [*range(15)], 24, False
			)
			chad.animation.add_by_indices(
				"dance_right", "bg dancer sketch PINK", [*range(15, 30)], 24, False
			)
			self._henchmen.append(chad)

		limo = self.create_object("limo", x=-120, y=550)
		limo.frames = load_frames("week4/images/limo/limoDrive.xml")
		limo.animation.add_by_prefix("drive", "Limo stage")
		limo.animation.play("drive")

		self.car = self.create_object("car", image=load_image("week4/images/limo/fastCarLol.png"))
		self._reset_car()

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		a = "dance_right" if self._henchmen_next_right else "dance_left"
		self._henchmen_next_right = not self._henchmen_next_right
		for chad in self._henchmen:
			chad.animation.play(a)

		if self._allow_passing_car and randint(0, 9) == 0:
			self._move_car()

	def _reset_car(self, *_) -> None:
		self.car.position = (-12600, randint(140, 250))
		self.car.stop_movement()
		self._allow_passing_car = True

	def _move_car(self) -> None:
		self._allow_passing_car = False
		self.sfx_ring.play(choice(self._car_sounds), 0.7)
		# Originally used dt which is accessible in a global field in FlxG cause of course it is.
		# Assume the sane default instead, i don't think it has much of an effect
		self.car.start_movement(((randint(170, 220) / 0.016666) * 3.0, 0))
		self.clock.schedule_once(self._reset_car, 2.0)
