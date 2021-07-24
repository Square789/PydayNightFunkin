
from pathlib import Path
import typing as t

import pyglet

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.image_loader import load_animation_frames_from_xml, load_image
from pyday_night_funkin.week import Level

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame


class Week1Level(Level):

	_unused_CAMERAS = {
		"main_cam": ("background0", "background1", "girlfriend", "stage", "curtains"),
		"ui_cam": ("ui", ),
	}

	def get_layer_names(self) -> t.Sequence[str]:
		return ("background0", "background1", "girlfriend", "stage", "curtains", "ui")

	def load_sprites(self, game_scene: "InGame") -> None:
		"""
		Loads sprites for all week 1 levels.
		"""
		game_scene.create_sprite(
			"background0",
			(-600, -100),
			load_image(Path(CNST.ASSETS, "shared/images/stageback.png")),
		)
		game_scene.create_sprite(
			"background1",
			(-650, 600),
			load_image(Path(CNST.ASSETS, "shared/images/stagefront.png")),
		)

		gf_anims = load_animation_frames_from_xml(Path(CNST.ASSETS, "shared/images/GF_assets.xml"))
		self.gf = game_scene.create_sprite("girlfriend", (400, 130), None)

		bf_anims = load_animation_frames_from_xml(Path(CNST.ASSETS, "shared/images/BOYFRIEND.xml"))
		self.bf = game_scene.create_sprite("stage", (770, 450), None)

		op_anims = load_animation_frames_from_xml(Path(CNST.ASSETS, "shared/images/DADDY_DEAREST.xml"))
		self.opponent = game_scene.create_sprite("stage", (100, 100), None)

		game_scene.create_sprite(
			"curtains",
			(-500, -300),
			load_image(Path(CNST.ASSETS, "shared/images/stagecurtains.png")),
		)

	def on_start(self) -> None:
		pass
		# self.gf.play_animation("idle_bop")
		# self.bf.play_animation("idle_bop")
		# self.opponent.play_animation("idle_bop")
