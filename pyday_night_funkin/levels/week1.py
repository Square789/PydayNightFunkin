
from itertools import product
import typing as t

import pyglet.clock

from pyday_night_funkin.asset_system import ASSETS, SONGS
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.health_bar import HealthBar
from pyday_night_funkin.levels import Level
from pyday_night_funkin.note import NOTE_TYPE
from pyday_night_funkin.pnf_sprite import TWEEN_ATTR
from pyday_night_funkin.scenes.in_game import IN_GAME_STATE
from pyday_night_funkin.tweens import in_out_cubic


class Week1Level(Level):

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ("main", "ui")

	@staticmethod
	def get_layer_names() -> t.Sequence[str]:
		return (
			"background0", "background1", "girlfriend", "stage", "curtains",
			"ui0", "ui1", "ui2", "ui3"
		)

	def load_resources(self) -> None:
		"""
		Loads sprites and sounds for all week 1 levels.
		"""
		self.game_scene.cameras["main"].zoom = 1.0

		# SPRITES
		stageback = self.game_scene.create_sprite(
			"background0", (-600, -200), ASSETS.IMG.STAGE_BACK.load(), "main"
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.game_scene.create_sprite(
			"background1", (-650, 600), ASSETS.IMG.STAGE_FRONT.load(), "main"
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.world_scale = 1.1

		gf_anims = ASSETS.XML.GIRLFRIEND.load()
		self.gf = self.game_scene.create_sprite("girlfriend", (400, 130), None, "main")
		self.gf.scroll_factor = (.95, .95)
		self.gf.add_animation("idle_bop", gf_anims["GF Dancing Beat"], 24, True)

		bf_anims = ASSETS.XML.BOYFRIEND.load()
		self.bf = self.game_scene.create_sprite("stage", (770, 450), None, "main")
		self.bf.add_animation("idle_bop", bf_anims["BF idle dance"], 24, True)
		# self.bf.scroll_factor = (0, 0)

		op_anims = ASSETS.XML.DADDY_DEAREST.load()
		self.opponent = self.game_scene.create_sprite("stage", (100, 100), None, "main")
		self.opponent.add_animation("idle_bop", op_anims["Dad idle dance"], 24, True)

		stagecurtains = self.game_scene.create_sprite(
			"curtains", (-500, -300), ASSETS.IMG.STAGE_CURTAINS.load(), "main"
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.world_scale = 0.9

		note_sprites = ASSETS.XML.NOTES.load()
		self.static_arrows = [{}, {}]
		for i, note_type in product((0, 1), NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			arrow_width = note_sprites[atlas_names[0]][0].texture.width
			x = 50 + (CNST.GAME_WIDTH // 2) * i + (note_type.get_order() * arrow_width * .7)
			y = CNST.STATIC_ARROW_Y
			arrow_sprite = self.game_scene.create_sprite("ui0", (x, y), None)
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				arrow_sprite.add_animation(anim_name, note_sprites[atlas_name], 24, False)
			arrow_sprite.world_scale = .7
			arrow_sprite.play_animation("static")
			self.static_arrows[i][note_type] = arrow_sprite

		self.health_bar = HealthBar(self.game_scene, "ui", "dad", "bf", ("ui0", "ui1", "ui2"))
		self.health_bar.update(self.game_scene.health)

		countdown_textures = (
			None,
			ASSETS.IMG.READY.load(),
			ASSETS.IMG.SET.load(),
			ASSETS.IMG.GO.load(),
		)
		self.countdown_sprites = []
		for tex in countdown_textures:
			if tex is None:
				self.countdown_sprites.append(None)
				continue

			sprite = self.game_scene.create_sprite(
				"ui0",
				((CNST.GAME_WIDTH - tex.width) // 2, (CNST.GAME_HEIGHT - tex.height) // 2),
				tex,
				"ui",
			)
			sprite.visible = False
			self.countdown_sprites.append(sprite)

		self.countdown_sounds = (
			ASSETS.SOUND.INTRO_3.load(),
			ASSETS.SOUND.INTRO_2.load(),
			ASSETS.SOUND.INTRO_1.load(),
			ASSETS.SOUND.INTRO_GO.load(),
		)


	def on_start(self) -> None:
		self.gf.play_animation("idle_bop")
		self.bf.play_animation("idle_bop")
		self.opponent.play_animation("idle_bop")

		self._countdown_stage = 0
		self.game_scene.state = IN_GAME_STATE.COUNTDOWN
		self.game_scene.conductor.song_position = self.game_scene.conductor.beat_duration * -5
		pyglet.clock.schedule_interval(
			self.countdown, self.game_scene.conductor.beat_duration / 1000
		)

	def countdown(self, _dt: float) -> None:
		if self._countdown_stage == 4:
			self.game_scene.start_song()
			pyglet.clock.unschedule(self.countdown)
		else:
			# self._countdown_stage will be changed once hide is called
			sprite_idx = self._countdown_stage
			if self.countdown_sprites[sprite_idx] is not None:
				def hide():
					self.countdown_sprites[sprite_idx].visible = False
				self.countdown_sprites[sprite_idx].visible = True
				self.countdown_sprites[sprite_idx].tween(
					in_out_cubic,
					TWEEN_ATTR.OPACITY,
					0,
					self.game_scene.conductor.beat_duration / 1000,
					hide
				)

			if self.countdown_sounds[sprite_idx] is not None:
				self.game_scene.sfx_ring.play(self.countdown_sounds[sprite_idx])

			self._countdown_stage += 1

