
from itertools import product
from pyday_night_funkin.characters import Boyfriend, DaddyDearest, Girlfriend
from loguru import logger
from random import randint
import typing as t

import pyglet.clock

from pyday_night_funkin.asset_system import ASSETS, OggVorbisSong
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.health_bar import HealthBar
from pyday_night_funkin.level import Level, GAME_STATE
from pyday_night_funkin.note import RATING, NOTE_TYPE
from pyday_night_funkin.note_handler import NoteHandler
from pyday_night_funkin.graphics.pnf_sprite import TWEEN_ATTR
from pyday_night_funkin.tweens import in_out_cubic, linear, out_cubic

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame


class Week1Level(Level):
	def __init__(self, game_scene: "InGame") -> None:
		super().__init__(game_scene)

		self.note_handler = NoteHandler(self, "ui1", "ui")

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ("main", "ui")

	@staticmethod
	def get_layer_names() -> t.Sequence[str]:
		return (
			"background0", "background1", "girlfriend", "stage", "curtains",
			"ui0", "ui1", "ui2", "ui3"
		)
		# ui0: static arrows, countdown sprite, health bar jpeg
		# ui1: notes, health bar bars
		# ui2: health bar icons

	def load_resources(self) -> None:
		"""
		Loads sprites and sounds for all week 1 levels.
		"""
		self.game_scene.cameras["main"].zoom = 1.0
		# self.game_scene.cameras["main"].y += 200

		# SPRITES
		stageback = self.game_scene.create_sprite(
			"background0", "main", x = -600, y = -200, image = ASSETS.IMG.STAGE_BACK.load()
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.game_scene.create_sprite(
			"background1", "main", x = -650, y = 600, image = ASSETS.IMG.STAGE_FRONT.load()
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.scale = 1.1

		self.gf = self.game_scene.create_sprite(
			"girlfriend", "main", Girlfriend, level = self, x = 400, y = 130, image = None
		)
		self.gf.scroll_factor = (.95, .95)

		self.bf = self.game_scene.create_sprite(
			"stage", "main", Boyfriend, level = self, x = 770, y = 450, image = None
		)

		self.opponent = self.game_scene.create_sprite(
			"stage", "main", DaddyDearest, level = self, x = 100, y = 100, image = None
		)

		stagecurtains = self.game_scene.create_sprite(
			"curtains", "main", x = -500, y = -300, image = ASSETS.IMG.STAGE_CURTAINS.load()
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.scale = 0.9

		note_sprites = ASSETS.XML.NOTES.load()
		self.static_arrows = [{}, {}]
		for i, note_type in product((0, 1), NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			arrow_width = note_sprites[atlas_names[0]][0].texture.width
			x = 50 + (CNST.GAME_WIDTH // 2) * i + (note_type.get_order() * arrow_width * .7)
			y = CNST.STATIC_ARROW_Y
			arrow_sprite = self.game_scene.create_sprite("ui0", "ui", x = x, y = y, image = None)
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				arrow_sprite.add_animation(anim_name, note_sprites[atlas_name], 24, False)
			arrow_sprite.scale = .7
			arrow_sprite.play_animation("static")
			self.static_arrows[i][note_type] = arrow_sprite

		self.health_bar = HealthBar(self.game_scene, "ui", "dad", "bf", ("ui0", "ui1", "ui2"))
		self.health_bar.update(self.health)

		self.countdown_textures = (
			None,
			ASSETS.IMG.READY.load(),
			ASSETS.IMG.SET.load(),
			ASSETS.IMG.GO.load(),
		)

		self.countdown_sounds = (
			ASSETS.SOUND.INTRO_3.load(),
			ASSETS.SOUND.INTRO_2.load(),
			ASSETS.SOUND.INTRO_1.load(),
			ASSETS.SOUND.INTRO_GO.load(),
		)

		self.note_rating_textures = {
			RATING.SICK: ASSETS.IMG.SICK.load(),
			RATING.GOOD: ASSETS.IMG.GOOD.load(),
			RATING.BAD: ASSETS.IMG.BAD.load(),
			RATING.SHIT: ASSETS.IMG.SHIT.load(),
		}

		self.number_textures = [getattr(ASSETS.IMG, f"NUM{i}").load() for i in range(10)]

	def load_song(self) -> None:
		self.note_handler.feed_song_data(super().load_song())

	def process_input(self, dt: float) -> None:
		pressed = {
			type_: self.key_handler.just_pressed(control)
			for type_, control in self.note_handler.NOTE_TO_CONTROL_MAP.items()
			if self.key_handler[control]
		}
		opponent_hit, player_missed, player_res = self.note_handler.update(pressed)

		if opponent_hit:
			op_note = opponent_hit[-1]
			self.opponent.hold_timer = 0.0
			self.opponent.play_animation(f"sing_note_{op_note.type.name.lower()}")

		if player_missed:
			fail_note = player_missed[-1]
			self.bf.play_animation(f"miss_note_{fail_note.type.name.lower()}")

		for type_ in NOTE_TYPE:
			# Note not being held, make the arrow static
			if type_ not in player_res:
				if self.static_arrows[1][type_].current_animation != "static":
					self.static_arrows[1][type_].play_animation("static")
			# Note was pressed but player missed
			elif player_res[type_] is None:
				if (
					self.static_arrows[1][type_].current_animation is not None and
					self.static_arrows[1][type_].current_animation == "static"
				):
					self.static_arrows[1][type_].play_animation("pressed")
				if pressed[type_]:
					# Just pressed
					self.bf.play_animation(f"miss_note_{type_.name.lower()}")
					self.combo = 0
			# Note was pressed and player hit
			else:
				player_res[type_].on_hit(
					self.conductor.song_position,
					self.game_scene.game.config.safe_window,
				)
				self.static_arrows[1][type_].play_animation("confirm")
				self.bf.hold_timer = 0.0
				self.bf.play_animation(f"sing_note_{type_.name.lower()}")
				self.combo += 1

				x = int(CNST.GAME_WIDTH * .55)

				combo_sprite = self.game_scene.create_sprite(
					"ui2",
					"ui",
					image = self.note_rating_textures[player_res[type_].rating],
				)
				combo_sprite.screen_center(CNST.GAME_DIMENSIONS)
				combo_sprite.x = x - 40
				combo_sprite.y -= 60
				combo_sprite.scale = 0.7

				self.game_scene.set_movement(combo_sprite, (0, -150), (0, 600))

				combo_sprite.tween(
					tween_func = out_cubic,
					attributes = {TWEEN_ATTR.OPACITY: 0},
					duration = 0.2,
					on_complete = (
						lambda combo_sprite = combo_sprite:
							self.game_scene.remove_sprite(combo_sprite)
					),
					start_delay = self.conductor.beat_duration * 0.001,
				)
	
				for i, digit in enumerate(f"{self.combo:>03}"):
					sprite = self.game_scene.create_sprite(
						"ui2", "ui", image = self.number_textures[int(digit)]
					)
					sprite.screen_center(CNST.GAME_DIMENSIONS)
					sprite.x = x + (43 * i) - 90
					sprite.y += 80
					sprite.scale = .5

					self.game_scene.set_movement(
						sprite, (randint(-5, 5), -randint(140, 160)), (0, randint(200, 300))
					)

					sprite.tween(
						tween_func = linear,
						attributes = {TWEEN_ATTR.OPACITY: 0},
						duration = 0.2,
						on_complete = lambda sprite = sprite: self.game_scene.remove_sprite(sprite),
						start_delay = self.conductor.beat_duration * 0.002,
					)

		self.bf.update_character(dt, bool(pressed))

	def ready(self) -> None:
		self.gf.play_animation("idle_bop")
		self.bf.play_animation("idle_bop")
		self.opponent.play_animation("idle_bop")

		self._countdown_stage = 0
		self.state = GAME_STATE.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		pyglet.clock.schedule_interval(
			self.countdown, self.conductor.beat_duration * 0.001
		)

	def update(self, dt: float) -> None:
		super().update(dt)
		# bf is handled in `process_input`
		self.gf.update_character(dt)
		self.opponent.update_character(dt)

	def countdown(self, dt: float) -> None:
		if self._countdown_stage == 4:
			self.start_song()
			pyglet.clock.unschedule(self.countdown)
		else:
			# self._countdown_stage will be changed once hide is called
			sprite_idx = self._countdown_stage
			tex = self.countdown_textures[sprite_idx]
			if tex is not None:
				sprite = self.game_scene.create_sprite(
					"ui0",
					"ui",
					x = (CNST.GAME_WIDTH - tex.width) // 2,
					y = (CNST.GAME_HEIGHT - tex.height) // 2,
					image = tex,
				)

				sprite.tween(
					in_out_cubic,
					{TWEEN_ATTR.OPACITY: 0},
					self.conductor.beat_duration * 0.001,
					lambda sprite = sprite: self.game_scene.remove_sprite(sprite),
				)

			if self.countdown_sounds[sprite_idx] is not None:
				self.game_scene.sfx_ring.play(self.countdown_sounds[sprite_idx])

			self._countdown_stage += 1


class Bopeebo(Week1Level):
	@staticmethod
	def get_song() -> OggVorbisSong:
		return ASSETS.SONG.BOPEEBO

class Fresh(Week1Level):
	@staticmethod
	def get_song() -> OggVorbisSong:
		return ASSETS.SONG.FRESH

class DadBattle(Week1Level):
	@staticmethod
	def get_song() -> OggVorbisSong:
		return ASSETS.SONG.DAD_BATTLE
