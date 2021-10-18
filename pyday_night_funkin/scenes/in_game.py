
import random
import typing as t

from loguru import logger
from pyglet.media import Player
from pyglet.media.player import PlayerGroup

from pyday_night_funkin.asset_system import load_asset
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin.enums import DIFFICULTY, GAME_STATE
from pyday_night_funkin.scenes.music_beat import MusicBeatScene
from pyday_night_funkin.scenes.pause import PauseScene

if t.TYPE_CHECKING:
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
	def __init__(self, game: "Game", difficulty: DIFFICULTY) -> None:
		super().__init__(game)

		self.draw_passthrough = False

		self.difficulty = difficulty

		self.key_handler = game.key_handler
		self.note_handler = self.create_note_handler()

		self.state = GAME_STATE.LOADING

		self.inst_player = Player()
		self.voice_player = Player()
		self.song_players = PlayerGroup((self.inst_player, self.voice_player))

		self.song_data = None

		self.health = 0.5
		self.combo = 0

		self.load_resources()
		self.load_song()
		self.ready()

	@staticmethod
	def get_song() -> int:
		raise NotImplementedError("Subclass this!")

	def create_note_handler(self) -> "AbstractNoteHandler":
		raise NotImplementedError("Subclass this!")

	def resync(self) -> None:
		logger.info("Resyncing...")
		self.voice_player.pause()
		# NOTE Conductor may be rewound here which has potential to screw things up
		self.conductor.song_position = self.inst_player.time * 1000
		self.voice_player.seek(self.conductor.song_position * 0.001)
		self.voice_player.play()

	def on_regular_update_change(self, new: bool) -> None:
		if self.state is not GAME_STATE.PLAYING:
			return

		if new:
			self.song_players.play()
		else:
			self.song_players.pause()

	def load_resources(self) -> None:
		"""
		This function will be called by the game scene in an early
		state of level setup # TODO DOC. Override it in a subclass!
		"""
		pass

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
		Called after `load_resources` and `load_song` have been called.
		Should be used to start the level.
		"""
		pass

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

		if self.key_handler.just_pressed(CONTROL.ENTER):
			self.game.push_scene(PauseScene)

	def process_input(self, dt: float) -> None:
		"""
		Called with `update` every time.
		Keyboard input should be handled here.
		"""
		if self.game.debug:
			if self.game.key_handler.just_pressed(CONTROL.DEBUG_DESYNC):
				desync = random.randint(-200, 200)
				logger.debug(f"Desyncing conductor by {desync}ms")
				self.conductor.song_position += desync
