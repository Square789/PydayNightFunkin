
from enum import IntEnum
import typing as t

from loguru import logger
from pyglet.media import Player
from pyglet.media.player import PlayerGroup

from pyday_night_funkin.asset_system import OggVorbisSong
from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.note_handler import NoteHandler

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame


class GAME_STATE(IntEnum):
	LOADING = 0
	START_DIALOGUE = 1
	COUNTDOWN = 2
	PLAYING = 3
	END_DIALOGUE = 4


class Level:
	"""
	Main game driver.
	Meant to be a jumble of sprites, players, handlers etc. running the
	entire game.
	Note that this base class only provides a very small shred of
	functionality, for it to be playable it needs to be expanded
	by subclassing it (see existing weeks for examples).
	"""

	def __init__(self, game_scene: "InGame") -> None:
		self.game_scene = game_scene

		self.key_handler = game_scene.game.key_handler

		self.state = GAME_STATE.LOADING

		self.inst_player = Player()
		self.voice_player = Player()
		self.song_players = PlayerGroup((self.inst_player, self.voice_player))

		self.conductor = Conductor()

		self.health = 0.5
		self.combo = 0

		self._updates_since_desync_warn = 999

	@staticmethod
	def get_song() -> OggVorbisSong:
		raise NotImplementedError("Subclass this!")

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ()

	@staticmethod
	def get_layer_names() -> t.Sequence[str]:
		return ()

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
		inst, voices, song_data = self.get_song().load(
			(False, False), self.game_scene.info.difficulty
		)
		self.song_players.pause()
		self.inst_player.next_source()
		self.inst_player.queue(inst)
		# self.inst_player.volume = 0
		# self.voice_player.volume = 0
		if voices is not None:
			self.voice_player.next_source()
			self.voice_player.queue(voices)

		self.conductor.bpm = song_data["song"]["bpm"]
		return song_data

	def start_song(self) -> None:
		"""
		Starts the song by making the players play, zeroing
		conductor's position and setting the state to PLAYING.
		"""
		self.conductor.song_position = 0
		self.song_players.play()

	def ready(self) -> None:
		"""
		Called after `load_resources` and `load_song` have been called.
		Should be used to start the level.
		"""
		pass

	def update(self, dt: float) -> None:
		if self.state is GAME_STATE.COUNTDOWN or self.state is GAME_STATE.PLAYING:
			self.conductor.song_position += dt * 1000
			discrepancy = self.inst_player.time * 1000 - self.conductor.song_position
			if abs(discrepancy) > 20 and self._updates_since_desync_warn > 100:
				logger.warning(f"Conductor out of sync with player by {discrepancy:.4f} ms.")
				self._updates_since_desync_warn = 0
			self._updates_since_desync_warn += 1

		self.process_input(dt)

	def process_input(self, dt: float) -> None:
		"""
		Called with `update` every time. Keyboard input should be
		handled here.
		"""
		pass
