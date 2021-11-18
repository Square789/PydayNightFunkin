
from math import floor
import random
import typing as t

from loguru import logger
from pyglet.math import Vec2
from pyglet.media import Player
from pyglet.media.player import PlayerGroup

from pyday_night_funkin.asset_system import load_asset
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin.enums import ANIMATION_TAG, DIFFICULTY, GAME_STATE
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.note import NOTE_TYPE, SUSTAIN_STAGE, Note
from pyday_night_funkin.scenes.mainmenu import MainMenuScene
from pyday_night_funkin.scenes.music_beat import MusicBeatScene
from pyday_night_funkin.scenes.pause import PauseScene
from pyday_night_funkin.scenes.title import TitleScene
from pyday_night_funkin.utils import lerp

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character, Boyfriend, Girlfriend
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class InGameScene(MusicBeatScene):
	"""
	Main game driver scene.
	Meant to be a jumble of sprites, players, handlers etc. running the
	entire game.
	Note that this base class only provides a very small shred of
	functionality, for it to be playable it needs to be expanded
	by subclassing it (see existing weeks for examples).
	"""
	def __init__(
		self,
		game: "Game",
		difficulty: DIFFICULTY,
		created_from: t.Union[t.Type[MainMenuScene], t.Type[TitleScene]],
	) -> None:
		super().__init__(game)

		if self.game.player.playing:
			self.game.player.pause()

		self.draw_passthrough = False

		self.difficulty = difficulty
		self.created_from = created_from

		self.key_handler = game.key_handler

		self.state = GAME_STATE.LOADING

		self.inst_player = Player()
		self.voice_player = Player()
		self.song_players = PlayerGroup((self.inst_player, self.voice_player))

		self.song_data = None

		self.health = 0.5
		self.combo = 0

		self._last_followed_singer = 0
		self.zoom_cams = False

		self.setup()
		self.load_song()
		self.ready()

	@staticmethod
	def get_song() -> int:
		"""
		Returns the scene's song's identifier as present in the assets.
		"""
		raise NotImplementedError("Subclass this!")

	@staticmethod
	def get_default_cam_zoom() -> float:
		"""
		Returns the default camera zoom.
		"""
		return 1.05

	# Override from BaseScene
	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ("main", "hud")

	@staticmethod
	def get_player_icon() -> str:
		"""
		Returns the player's health bar icon.
		"""
		return "bf"

	@staticmethod
	def get_opponent_icon() -> str:
		"""
		Returns the opponent's health bar icon.
		"""
		raise NotImplementedError("Subclass this!")

	@classmethod
	def get_display_name(cls) -> str:
		"""
		Returns the display name for this level.
		Should be free of any special characters that the default
		alphabet can't handle. By default, returns the class's name.
		"""
		return cls.__name__

	def create_note_handler(self) -> "AbstractNoteHandler":
		raise NotImplementedError("Subclass this!")

	def create_hud(self) -> "HUD":
		raise NotImplementedError("Subclass this!")

	def create_boyfriend(self) -> "Boyfriend":
		"""
		Creates bf, or any sort of player sprite for that matter.
		By default, the sprite is expected to have the following
		animations:
		`idle_bop`, `[x]_note_[y]` for x in (`sing`, `miss`)
		and y in (`left`, `down`, `right`, `up`).
		"""
		raise NotImplementedError("Subclass this!")

	def create_girlfriend(self) -> "Girlfriend":
		"""
		Creates gf. This sprite is expected to have the following
		animations:
		`idle_bop`
		"""
		raise NotImplementedError("Subclass this!")

	def create_opponent(self) -> "Character":
		raise NotImplementedError("Subclass this!")

	def setup(self) -> None:
		"""
		Sets up the game scene.
		By default, this function calls:
		`create_[boyfriend|girlfriend|opponent|hud|note_handler]`.
		Override it (and don't forget `super().setup()`) to add custom
		game scene code (backgrounds etc.)
		"""
		self.note_handler = self.create_note_handler()

		self.boyfriend = self.create_boyfriend()
		self.girlfriend = self.create_girlfriend()
		self.opponent = self.create_opponent()

		self.main_cam = self.cameras["main"]
		self.hud_cam = self.cameras["hud"]

		self.hud = self.create_hud()

	def resync(self) -> None:
		logger.info("Resyncing...")
		self.voice_player.pause()
		# TODO: Conductor may be rewound here which has potential to screw things up
		self.conductor.song_position = self.inst_player.time * 1000
		self.voice_player.seek(self.conductor.song_position * 0.001)
		self.voice_player.play()

	def load_song(self) -> t.Dict:
		"""
		# TODO doc
		"""
		inst, voices, song_data = load_asset(
			self.get_song(), (False, False), self.difficulty
		)

		self.song_players.pause()
		self.inst_player.next_source()
		self.inst_player.queue(inst)
		# self.inst_player.volume = 0
		# self.voice_player.volume = 0
		if voices is not None:
			self.voice_player.next_source()
			self.voice_player.queue(voices)

		self.conductor.bpm = song_data["bpm"]
		self.conductor.load_bpm_changes(song_data)
		self.note_handler.feed_song_data(song_data)

		self.song_data = song_data

	def start_song(self) -> None:
		"""
		Starts the song by making the players play, zeroing
		conductor's position and setting the state to PLAYING.
		"""
		self.conductor.song_position = 0
		self.song_players.play()
		self.state = GAME_STATE.PLAYING

	def ready(self) -> None:
		"""
		Called after `setup` and `load_song` have been called.
		Should be used to start the level.
		"""
		self.girlfriend.animation.play("idle_bop")
		self.boyfriend.animation.play("idle_bop")
		self.opponent.animation.play("idle_bop")
		self.opponent.check_animation_controller() # for the `main_cam.look_at` below

		self.main_cam.zoom = self.get_default_cam_zoom()
		self.main_cam.look_at(self.opponent.get_midpoint() + Vec2(400, 0))

		self._countdown_stage = 0
		self.state = GAME_STATE.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		self.clock.schedule_interval(
			self.countdown, self.conductor.beat_duration * 0.001
		)

	def update(self, dt: float) -> None:
		super().update(dt)

		if (
			self.state is GAME_STATE.COUNTDOWN or
			self.state is GAME_STATE.PLAYING
		):
			self.conductor.song_position += dt * 1000
			if self.state is GAME_STATE.PLAYING:
				discrepancy = self.inst_player.time * 1000 - self.conductor.song_position
				if abs(discrepancy) > 20:
					logger.warning(f"Player ahead of conductor by {discrepancy:.4f} ms.")
					self.resync()

		self.process_input(dt)

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
						_cam_follow = self.boyfriend.get_midpoint() + Vec2(-100, -100)
					self.main_cam.set_follow_target(_cam_follow, 0.04)

		if self.zoom_cams:
			self.main_cam.zoom = lerp(self.get_default_cam_zoom(), self.main_cam.zoom, 0.95)
			self.hud_cam.zoom = lerp(1.0, self.hud_cam.zoom, 0.95)

	def process_input(self, dt: float) -> None:
		"""
		Called with `update` every time.
		Keyboard input should be handled here.
		"""
		pressed = {
			type_: self.key_handler.just_pressed(control)
			for type_, control in self.note_handler.NOTE_TO_CONTROL_MAP.items()
			if self.key_handler[control]
		}
		opponent_hit, player_missed, player_res = self.note_handler.update(pressed)

		if opponent_hit:
			op_note = opponent_hit[-1]
			# self.opponent.on_hit(op_note)
			self.opponent.hold_timer = 0.0
			self.opponent.animation.play(f"sing_note_{op_note.type.name.lower()}", True)
			self.zoom_cams = True

		if player_missed:
			for note in player_missed:
				self.on_note_miss(note)
			fail_note = player_missed[-1]
			# self.boyfriend.on_miss(fail_note)
			self.boyfriend.animation.play(f"miss_note_{fail_note.type.name.lower()}", True)

		for type_ in NOTE_TYPE:
			# Note not being held, make the arrow static
			if type_ not in player_res:
				self.hud.arrow_static(type_)
			# Note was pressed but player missed
			elif player_res[type_] is None:
				self.hud.arrow_pressed(type_)
				if pressed[type_]: # Just pressed
					self.on_misinput(type_)
			# Note was pressed and player hit
			else:
				self.hud.arrow_confirm(type_)
				self.on_note_hit(player_res[type_])

		self.boyfriend.dont_idle = bool(pressed)

		if self.game.debug:
			if self.game.key_handler.just_pressed(CONTROL.DEBUG_DESYNC):
				desync = random.randint(-200, 200)
				logger.debug(f"Desyncing conductor by {desync}ms")
				self.conductor.song_position += desync

		if self.key_handler.just_pressed(CONTROL.ENTER):
			self.song_players.pause()
			self.game.push_scene(PauseScene)

	def on_note_hit(self, note: Note) -> None:
		"""
		Called whenever a note is hit.
		"""
		note.on_hit(self.conductor.song_position, self.game.config.safe_window)
		# self.boyfriend.on_hit(type_)
		self.boyfriend.hold_timer = 0.0
		self.boyfriend.animation.play(f"sing_note_{note.type.name.lower()}", True)

		if note.sustain_stage is SUSTAIN_STAGE.NONE:
			self.combo += 1
			self.hud.combo_popup(note.rating, self.combo)

	def on_note_miss(self, note: Note) -> None:
		"""
		Called whenever a note is missed by it going offscreen.
		"""
		pass

	def on_misinput(self, type_: NOTE_TYPE) -> None: # CALM DOWN CALM DOWN
		"""
		Called whenever an arrow is pressed and no note for it was
		playable.
		"""
		self.boyfriend.animation.play(f"miss_note_{type_.name.lower()}", True)
		self.combo = 0

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.zoom_cams and self.main_cam.zoom < 1.35 and self.cur_beat % 4 == 0:
			self.main_cam.zoom += 0.015
			self.hud_cam.zoom += 0.03

		if not self.boyfriend.animation.has_tag(ANIMATION_TAG.SING):
			self.boyfriend.animation.play("idle_bop")

	def countdown(self, dt: float) -> None:
		if self._countdown_stage == 4:
			self.start_song()
			self.clock.unschedule(self.countdown)
		else:
			# self._countdown_stage will be changed once hide is called
			self.hud.countdown_popup(self._countdown_stage)
			self._countdown_stage += 1

	def remove_subscene(self, end_self, *a, **kw):
		super().remove_subscene(*a, **kw)
		if end_self:
			self.game.set_scene(self.created_from)
		else:
			if self.state is GAME_STATE.PLAYING:
				self.song_players.play()
				self.resync()

	def destroy(self) -> None:
		super().destroy()
		self.voice_player.delete()
		self.inst_player.delete()
