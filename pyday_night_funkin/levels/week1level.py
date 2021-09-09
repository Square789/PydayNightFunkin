
from itertools import product
from loguru import logger
from random import randint
import typing as t

import pyglet.clock

from pyday_night_funkin.asset_system import ASSETS, SONGS, OggVorbisSong
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.health_bar import HealthBar
from pyday_night_funkin.level import Level, GAME_STATE
from pyday_night_funkin.note import RATING, NOTE_TYPE
from pyday_night_funkin.note_handler import NoteHandler
from pyday_night_funkin.pnf_sprite import TWEEN_ATTR
from pyday_night_funkin.tweens import in_cubic, in_out_cubic, linear, out_cubic

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame

# TODO: probably put another "BaseGame" level between this one and
# "Level", or something to eliminate code dup for commonly reused sprites.

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

	def load_resources(self) -> None:
		"""
		Loads sprites and sounds for all week 1 levels.
		"""
		self.game_scene.cameras["main"].zoom = 1.0
		self.game_scene.cameras["main"].y += 200

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
		self.bf.add_animation("idle_bop", bf_anims["BF idle dance"], 24, True, (-5, 0))
		self.bf.add_animation("note_left", bf_anims["BF NOTE LEFT"], 24, False, (12, -6))
		self.bf.add_animation("note_left_miss", bf_anims["BF NOTE LEFT MISS"], 24, False, (12, 24))
		self.bf.add_animation("note_down", bf_anims["BF NOTE DOWN"], 24, False, (-10, -50))
		self.bf.add_animation("note_down_miss", bf_anims["BF NOTE DOWN MISS"], 24, False, (-11, -19))
		self.bf.add_animation("note_up", bf_anims["BF NOTE UP"], 24, False, (-29, 27))
		self.bf.add_animation("note_up_miss", bf_anims["BF NOTE UP MISS"], 24, False, (-29, 27))
		self.bf.add_animation("note_right", bf_anims["BF NOTE RIGHT"], 24, False, (-38, -7))
		self.bf.add_animation("note_right_miss", bf_anims["BF NOTE RIGHT MISS"], 24, False, (-30, 21))

		op_anims = ASSETS.XML.DADDY_DEAREST.load()
		self.opponent = self.game_scene.create_sprite("stage", (100, 100), None, "main")
		self.opponent.add_animation("idle_bop", op_anims["Dad idle dance"], 24, True)
		self.opponent.add_animation("note_left", op_anims["Dad Sing Note LEFT"], 24, False, (-10, 10))
		self.opponent.add_animation("note_down", op_anims["Dad Sing Note DOWN"], 24, False, (0, -30))
		self.opponent.add_animation("note_up", op_anims["Dad Sing Note UP"], 24, False, (-6, 50))
		self.opponent.add_animation("note_right", op_anims["Dad Sing Note RIGHT"], 24, False, (0, 27))

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
			arrow_sprite._fixed_graphics_size = (150, 150)
			self.static_arrows[i][note_type] = arrow_sprite

		self.health_bar = HealthBar(self.game_scene, "ui", "dad", "bf", ("ui0", "ui1", "ui2"))
		self.health_bar.update(self.health)

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

		self.note_rating_sprites = {
			RATING.SICK: ASSETS.IMG.SICK.load(),
			RATING.GOOD: ASSETS.IMG.GOOD.load(),
			RATING.BAD: ASSETS.IMG.BAD.load(),
			RATING.SHIT: ASSETS.IMG.SHIT.load(),
		}

		self.number_sprites = [getattr(ASSETS.IMG, f"NUM{i}").load() for i in range(10)]

	def process_input(self) -> None:
		pressed = {
			type_: self.key_handler.just_pressed(control)
			for type_, control in self.note_handler.NOTE_TO_CONTROL_MAP.items()
			if self.key_handler[control]
		}
		opponent_hit, player_missed, player_res = self.note_handler.update(pressed)

		if opponent_hit:
			op_note = opponent_hit[-1]
			self.opponent.play_animation(f"note_{op_note.type.name.lower()}")

		if player_missed:
			fail_note = player_missed[-1]
			self.bf.play_animation(f"note_{fail_note.type.name.lower()}_miss")

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
					self.bf.play_animation(f"note_{type_.name.lower()}_miss")
					self.combo = 0
			# Note was pressed and player hit
			else:
				player_res[type_].on_hit(
					self.conductor.song_position,
					self.game_scene.game.config.safe_window
				)
				self.static_arrows[1][type_].play_animation("confirm")
				self.bf.play_animation(f"note_{type_.name.lower()}")
				self.combo += 1

				x = int(CNST.GAME_WIDTH * .55)

				combo_sprite = self.game_scene.create_sprite(
					"ui2",
					image = self.note_rating_sprites[player_res[type_].rating],
				)
				combo_sprite.screen_center(CNST.GAME_DIMENSIONS)
				combo_sprite.world_x = x - 40
				combo_sprite.world_y -= 60
				combo_sprite.world_scale = 0.7

				self.game_scene.set_movement(combo_sprite, (0, -150), (0, 600))

				combo_sprite.tween(
					tween_func = out_cubic,
					attributes = {TWEEN_ATTR.OPACITY: 0},
					duration = 0.2,
					on_complete = lambda: self.game_scene.remove_sprite(combo_sprite),
					start_delay = self.conductor.beat_duration * 0.001,
				)
	
				for i, digit in enumerate(f"{self.combo:>03}"):
					sprite = self.game_scene.create_sprite(
						"ui2", image = self.number_sprites[int(digit)], camera = "ui"
					)
					sprite.screen_center(CNST.GAME_DIMENSIONS)
					sprite.world_x = x + (43 * i) - 90
					sprite.world_y += 80
					sprite.world_scale = .5

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

	def ready(self) -> None:
		self.gf.play_animation("idle_bop")
		self.bf.play_animation("idle_bop")
		self.opponent.play_animation("idle_bop")

		self._countdown_stage = 0
		self.state = GAME_STATE.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		pyglet.clock.schedule_interval(
			self.countdown, self.conductor.beat_duration / 1000
		)

	def countdown(self, _dt: float) -> None:
		if self._countdown_stage == 4:
			self.start_song()
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
					{TWEEN_ATTR.OPACITY: 0},
					self.conductor.beat_duration / 1000,
					hide,
				)

			if self.countdown_sounds[sprite_idx] is not None:
				self.game_scene.sfx_ring.play(self.countdown_sounds[sprite_idx])

			self._countdown_stage += 1


class Bopeebo(Week1Level):
	@staticmethod
	def get_song() -> OggVorbisSong:
		return SONGS["Bopeebo"]

class Fresh(Week1Level):
	@staticmethod
	def get_song() -> OggVorbisSong:
		return SONGS["Fresh"]

class DadBattle(Week1Level):
	@staticmethod
	def get_song() -> OggVorbisSong:
		return SONGS["Dad Battle"]
