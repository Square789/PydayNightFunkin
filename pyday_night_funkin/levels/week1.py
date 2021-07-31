
from loguru import logger
from pyday_night_funkin.health_bar import HealthBar
import typing as t

import pyglet.clock
from pyglet.media import Player, StaticSource, load

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.pnf_sprite import TWEEN_ATTR
from pyday_night_funkin.image_loader import load_animation_frames_from_xml, load_image
from pyday_night_funkin.levels import Level
from pyday_night_funkin.tweens import TWEEN


class Week1Level(Level):

	def get_camera_names(self) -> t.Sequence[str]:
		return ("main", "ui")

	def get_layer_names(self) -> t.Sequence[str]:
		return (
			"background0", "background1", "girlfriend", "stage", "curtains",
			"ui0", "ui1", "ui2", "ui3"
		)

	def load_sprites(self) -> None:
		"""
		Loads sprites for all week 1 levels.
		"""
		self.game_scene.cameras["main"].zoom = 0.9

		# SPRITES
		stageback = self.game_scene.create_sprite(
			"background0",
			(-600, -100),
			load_image(CNST.ASSETS / "shared/images/stageback.png"),
			"main"
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.game_scene.create_sprite(
			"background1",
			(-650, 600),
			load_image(CNST.ASSETS / "shared/images/stagefront.png"),
			"main"
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.world_scale = 1.1

		gf_anims = load_animation_frames_from_xml(CNST.ASSETS / "shared/images/GF_assets.xml")
		self.gf = self.game_scene.create_sprite("girlfriend", (400, 130), None, "main")
		self.gf.scroll_factor = (.95, .95)
		self.gf.add_animation("idle_bop", gf_anims["GF Dancing Beat"], 24, True)

		bf_anims = load_animation_frames_from_xml(CNST.ASSETS / "shared/images/BOYFRIEND.xml")
		self.bf = self.game_scene.create_sprite("stage", (770, 450), None, "main")
		self.bf.add_animation("idle_bop", bf_anims["BF idle dance"], 24, True)

		op_anims = load_animation_frames_from_xml(CNST.ASSETS / "shared/images/DADDY_DEAREST.xml")
		self.opponent = self.game_scene.create_sprite("stage", (100, 100), None, "main")
		self.opponent.add_animation("idle_bop", op_anims["Dad idle dance"], 24, True)

		stagecurtains = self.game_scene.create_sprite(
			"curtains",
			(-500, -300),
			load_image(CNST.ASSETS / "shared/images/stagecurtains.png"),
			"main"
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.world_scale = 0.9

		note_sprites = load_animation_frames_from_xml(
			CNST.ASSETS / "shared/images/NOTE_assets.xml"
		)
		self.health_bar = HealthBar(self.game_scene, "ui", "dad", "bf", ("ui0", "ui1", "ui2"))
		self.health_bar.update(self.game_scene.health)

		countdown_textures = (
			load_image(CNST.ASSETS / "shared/images/ready.png"),
			load_image(CNST.ASSETS / "shared/images/set.png"),
			load_image(CNST.ASSETS / "shared/images/go.png"),
		)
		self.countdown_sprites = [
			self.game_scene.create_sprite(
				"ui0",
				((CNST.GAME_WIDTH - tex.width) // 2, (CNST.GAME_HEIGHT - tex.height) // 2),
				tex,
				"ui",
			) for tex in countdown_textures
		]
		for sprite in self.countdown_sprites:
			sprite.visible = False

		# SOUNDS
		song_dir = CNST.ASSETS / self.info.song_dir
		# self.snd_instrumental = StaticSource(load(str(song_dir / "Inst.wav")))
		# self.snd_voices = StaticSource(load(str(song_dir / "Voices.wav")))


	def on_start(self) -> None:
		self.gf.play_animation("idle_bop")
		self.bf.play_animation("idle_bop")
		self.opponent.play_animation("idle_bop")

		self._countdown_stage = 0
		pyglet.clock.schedule_interval(self.countdown, 1.0)

	def countdown(self, _dt: float) -> None:
		if self._countdown_stage == 3:
			self.start_song()
		else:
			# self._countdown_stage will be changed once hide is called
			sprite_idx = self._countdown_stage
			def hide():
				self.countdown_sprites[sprite_idx].visible = False
			self.countdown_sprites[sprite_idx].visible = True
			self.countdown_sprites[sprite_idx].tween(
				TWEEN.IN_OUT_CUBIC, TWEEN_ATTR.OPACITY, 0, 1.0, hide
			)

			self._countdown_stage += 1

	def start_song(self) -> None:
		pass
