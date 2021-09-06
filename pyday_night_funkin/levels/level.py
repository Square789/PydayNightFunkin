
from dataclasses import dataclass
from enum import IntEnum
import math
import typing as t

from loguru import logger
from pyglet.media import Player
from pyglet.media.player import PlayerGroup

from pyday_night_funkin.asset_system import SONGS, OggVorbisSong
from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.note import Note, NOTE_TYPE, SUSTAIN_STAGE
from pyday_night_funkin.note_handler import NoteHandler
from pyday_night_funkin.utils import ListWindow

if t.TYPE_CHECKING:
	from pyglet.media import Source
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
	Meant to be a subclassable jumble of sprites, players etc. running
	the entire game.
	For customization, subclass it (see existing weeks for examples).
	"""

	def __init__(self, game_scene: "InGame") -> None:
		self.game_scene = game_scene

		self.state = GAME_STATE.LOADING

		self.inst_player = Player()
		self.voice_player = Player()
		self.song_players = PlayerGroup((self.inst_player, self.voice_player))

		self.conductor = Conductor()

		self.health = 0.5
		self.note_handler = NoteHandler(self)

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

	def load_song(self) -> t.Tuple["Source", t.Optional["Source"], t.Dict[str, t.Any]]:
		"""
		# TODO doc
		"""
		inst, voices, song_data = self.get_song().load(
			(False, False), self.game_scene.info.difficulty
		)
		self.song_players.pause()
		self.inst_player.next_source()
		self.inst_player.queue(inst)
		if voices is not None:
			self.voice_player.next_source()
			self.voice_player.queue(voices)

		self.conductor.bpm = song_data["song"]["bpm"]
		self.note_handler.feed_song_data(song_data)

	def start_song(self) -> None:
		"""
		Starts the song by making the players play, zeroing
		conductor's position and setting the s state to PLAYING.
		"""
		logger.debug(f"Started song! Scroll speed: {self.note_handler.scroll_speed}")
		self.conductor.song_position = 0
		self.song_players.play()

	def ready(self) -> None:
		pass

	def update(self, dt: float) -> None:
		if self.state is GAME_STATE.COUNTDOWN or self.state is GAME_STATE.PLAYING:
			self.conductor.song_position += dt * 1000
			discrepancy = self.inst_player.time * 1000 - self.conductor.song_position
			if abs(discrepancy) > 20 and self._updates_since_desync_warn > 100:
				logger.warning(f"Conductor out of sync with player by {discrepancy:.4f} ms.")
				self._updates_since_desync_warn = 0
			self._updates_since_desync_warn += 1
			self.note_handler.update(dt)
