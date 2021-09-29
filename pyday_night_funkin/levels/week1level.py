
from itertools import product
from loguru import logger
from math import floor
from random import randint
import typing as t

import pyglet.clock
from pyglet.math import Vec2

from pyday_night_funkin.asset_system import ASSETS, load_asset
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.characters import Boyfriend, DaddyDearest, Girlfriend
from pyday_night_funkin.enums import GAME_STATE
from pyday_night_funkin.health_bar import HealthBar
from pyday_night_funkin.scenes import InGameScene
from pyday_night_funkin.note import RATING, NOTE_TYPE
from pyday_night_funkin.note_handler import AbstractNoteHandler, NoteHandler
from pyday_night_funkin.tweens import TWEEN_ATTR, in_out_cubic, linear, out_cubic
from pyday_night_funkin.utils import lerp


class Week1Level(InGameScene):
	DEFAULT_CAM_ZOOM = 0.9

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self._last_followed_singer = 0
		self.zoom_cams = False

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

	def create_note_handler(self) -> AbstractNoteHandler:
		return NoteHandler(self, "ui1", "ui")

	def load_resources(self) -> None:
		"""
		Loads sprites and sounds for all week 1 levels.
		"""
		# SPRITES
		stageback = self.create_sprite(
			"background0", "main", x = -600, y = -200, image = load_asset(ASSETS.IMG.STAGE_BACK)
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.create_sprite(
			"background1", "main", x = -650, y = 600, image = load_asset(ASSETS.IMG.STAGE_FRONT)
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.scale = 1.1

		self.gf = self.create_sprite(
			"girlfriend", "main", Girlfriend, scene = self, x = 400, y = 130, image = None
		)
		self.gf.scroll_factor = (.95, .95)

		self.bf = self.create_sprite(
			"stage", "main", Boyfriend, scene = self, x = 770, y = 450, image = None
		)

		self.opponent = self.create_sprite(
			"stage", "main", DaddyDearest, scene = self, x = 100, y = 100, image = None
		)

		stagecurtains = self.create_sprite(
			"curtains", "main", x = -500, y = -300, image = load_asset(ASSETS.IMG.STAGE_CURTAINS)
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.scale = 0.9

		note_sprites = load_asset(ASSETS.XML.NOTES)
		self.static_arrows = [{}, {}]
		for i, note_type in product((0, 1), NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			arrow_width = note_sprites[atlas_names[0]][0].texture.width
			x = 50 + (CNST.GAME_WIDTH // 2) * i + (note_type.get_order() * arrow_width * .7)
			y = CNST.STATIC_ARROW_Y
			arrow_sprite = self.create_sprite("ui0", "ui", x = x, y = y, image = None)
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				arrow_sprite.add_animation(anim_name, note_sprites[atlas_name], 24, False)
			arrow_sprite.scale = .7
			arrow_sprite.play_animation("static")
			self.static_arrows[i][note_type] = arrow_sprite

		self.health_bar = HealthBar(self, "ui", "dad", "bf", ("ui0", "ui1", "ui2"))
		self.health_bar.update(self.health)

		self.countdown_textures = (
			None,
			load_asset(ASSETS.IMG.READY),
			load_asset(ASSETS.IMG.SET),
			load_asset(ASSETS.IMG.GO),
		)

		self.countdown_sounds = (
			load_asset(ASSETS.SOUND.INTRO_3),
			load_asset(ASSETS.SOUND.INTRO_2),
			load_asset(ASSETS.SOUND.INTRO_1),
			load_asset(ASSETS.SOUND.INTRO_GO),
		)

		self.note_rating_textures = {
			RATING.SICK: load_asset(ASSETS.IMG.SICK),
			RATING.GOOD: load_asset(ASSETS.IMG.GOOD),
			RATING.BAD: load_asset(ASSETS.IMG.BAD),
			RATING.SHIT: load_asset(ASSETS.IMG.SHIT),
		}

		self.number_textures = [load_asset(getattr(ASSETS.IMG, f"NUM{i}")) for i in range(10)]

	def ready(self) -> None:
		self.gf.play_animation("idle_bop")
		self.bf.play_animation("idle_bop")
		self.opponent.play_animation("idle_bop")

		# No idea if this is a good choice but the dict accesses seem weird and
		# it's not like there will be more than these cameras
		self.main_cam = self.cameras["main"]
		self.ui_cam = self.cameras["ui"]

		self.main_cam.zoom = self.DEFAULT_CAM_ZOOM
		self.main_cam.look_at(self.opponent.get_midpoint() + Vec2(400, 0))

		self._countdown_stage = 0
		self.state = GAME_STATE.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		pyglet.clock.schedule_interval(
			self.countdown, self.conductor.beat_duration * 0.001
		)

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
			self.opponent.play_animation(f"sing_note_{op_note.type.name.lower()}", True)
			self.zoom_cams = True

		if player_missed:
			fail_note = player_missed[-1]
			self.bf.play_animation(f"miss_note_{fail_note.type.name.lower()}", True)

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
					self.bf.play_animation(f"miss_note_{type_.name.lower()}", True)
					self.combo = 0
			# Note was pressed and player hit
			else:
				player_res[type_].on_hit(
					self.conductor.song_position,
					self.game.config.safe_window,
				)
				self.static_arrows[1][type_].play_animation("confirm")
				self.bf.hold_timer = 0.0
				self.bf.play_animation(f"sing_note_{type_.name.lower()}")
				self.combo += 1

				x = int(CNST.GAME_WIDTH * .55)

				combo_sprite = self.create_sprite(
					"ui2",
					"ui",
					image = self.note_rating_textures[player_res[type_].rating],
				)
				combo_sprite.screen_center(CNST.GAME_DIMENSIONS)
				combo_sprite.x = x - 40
				combo_sprite.y -= 60
				combo_sprite.scale = 0.7

				self.start_movement(combo_sprite, (0, -150), (0, 600))

				self.start_tween(
					combo_sprite,
					tween_func = out_cubic,
					attributes = {TWEEN_ATTR.OPACITY: 0},
					duration = 0.2,
					on_complete = (
						lambda combo_sprite = combo_sprite: self.remove_sprite(combo_sprite)
					),
					start_delay = self.conductor.beat_duration * 0.001,
				)
	
				for i, digit in enumerate(f"{self.combo:>03}"):
					sprite = self.create_sprite(
						"ui2", "ui", image = self.number_textures[int(digit)]
					)
					sprite.screen_center(CNST.GAME_DIMENSIONS)
					sprite.x = x + (43 * i) - 90
					sprite.y += 80
					sprite.scale = .5

					self.start_movement(
						sprite, (randint(-5, 5), -randint(140, 160)), (0, randint(200, 300))
					)

					self.start_tween(
						sprite,
						tween_func = linear,
						attributes = {TWEEN_ATTR.OPACITY: 0},
						duration = 0.2,
						on_complete = lambda sprite = sprite: self.remove_sprite(sprite),
						start_delay = self.conductor.beat_duration * 0.002,
					)

		self.bf.update_character(dt, bool(pressed))

	def update(self, dt: float) -> None:
		super().update(dt)
		# bf is handled in `process_input`
		self.gf.update_character(dt)
		self.opponent.update_character(dt)

		# Camera follow code with crap indentation
		if self.song_data is not None:
			sec = floor(self.cur_step / 16)
			if sec >= 0 and sec < len(self.song_data["notes"]):
				cur_section = self.song_data["notes"][sec]
				to_follow = int(cur_section["mustHitSection"])
				if to_follow != self._last_followed_singer:
					self._last_followed_singer = to_follow
					if to_follow == 0:
						_cam_follow = self.opponent.get_midpoint() + Vec2(150, -100)
					else:
						_cam_follow = self.bf.get_midpoint() + Vec2(-100, -100)
					self.main_cam.set_follow_target(_cam_follow, 0.04)

		if self.zoom_cams:
			self.main_cam.zoom = lerp(self.DEFAULT_CAM_ZOOM, self.main_cam.zoom, 0.95)
			self.ui_cam.zoom = lerp(1.0, self.ui_cam.zoom, 0.95)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.zoom_cams and self.main_cam.zoom < 1.35 and self.cur_beat % 4 == 0:
			self.main_cam.zoom += 0.015
			self.ui_cam.zoom += 0.03

		if (
			self.bf.current_animation is not None and
			not self.bf.current_animation.startswith("sing")
		):
			self.bf.play_animation("idle_bop")

	def countdown(self, dt: float) -> None:
		if self._countdown_stage == 4:
			self.start_song()
			pyglet.clock.unschedule(self.countdown)
		else:
			# self._countdown_stage will be changed once hide is called
			sprite_idx = self._countdown_stage
			tex = self.countdown_textures[sprite_idx]
			if tex is not None:
				sprite = self.create_sprite(
					"ui0",
					"ui",
					x = (CNST.GAME_WIDTH - tex.width) // 2,
					y = (CNST.GAME_HEIGHT - tex.height) // 2,
					image = tex,
				)

				self.start_tween(
					sprite,
					in_out_cubic,
					{TWEEN_ATTR.OPACITY: 0},
					self.conductor.beat_duration * 0.001,
					lambda sprite = sprite: self.remove_sprite(sprite),
				)

			if self.countdown_sounds[sprite_idx] is not None:
				self.sfx_ring.play(self.countdown_sounds[sprite_idx])

			self._countdown_stage += 1


class Bopeebo(Week1Level):
	@staticmethod
	def get_song() -> int:
		return ASSETS.SONG.BOPEEBO

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.cur_beat % 8 == 7:
			self.bf.play_animation("hey")

class Fresh(Week1Level):
	@staticmethod
	def get_song() -> int:
		return ASSETS.SONG.FRESH

class DadBattle(Week1Level):
	@staticmethod
	def get_song() -> int:
		return ASSETS.SONG.DAD_BATTLE
