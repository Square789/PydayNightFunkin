
from dataclasses import dataclass
import typing as t

from pyglet.media import Player
from pyglet.media.player import PlayerGroup
from pyglet.window import key

from pyday_night_funkin.constants import DIFFICULTY
from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.scenes._base import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.levels import Week


@dataclass
class InGameInfo():
	difficulty: DIFFICULTY


class InGame(BaseScene):
	def __init__(self, game: "Game", week: "Week", level_index: int, info: InGameInfo) -> None:
		self.info = info

		self.level_blueprint = week[level_index]
		level_cls = self.level_blueprint.class_
		super().__init__(game, level_cls.get_layer_names(), level_cls.get_camera_names())

		self.level = self.level_blueprint.create_level(self)

		self.inst_player = Player()
		self.voice_player = Player()
		self.song_players = PlayerGroup((self.inst_player, self.voice_player))

		self.song_data = None
		self.conductor = Conductor()
		self._setup_song()

		self.health = 0.5

		self.level.load_resources()

		self.level.on_start()

	def play_song(self) -> None:
		self.song_players.play()

	def _setup_song(self) -> None:
		"""
		Queues the two song sources (out of which the second one may
		be None) as returned by `load_song` in the players and
		configures the conductor with the song's metadata.
		"""
		inst, voices, song_data = self.level.load_song()
		self.song_players.pause()
		self.inst_player.queue(inst)
		self.inst_player.next_source()
		if voices is not None:
			self.voice_player.queue(voices)
			self.voice_player.next_source()
		self.song_data = song_data
		self.conductor.bpm = song_data["song"]["bpm"]

	def update(self, dt: float) -> None:
		if self.game.ksh[key.Q]:
			self.health += 0.02
			self.level.health_bar.update(self.health)
		if self.game.ksh[key.E]:
			self.health -= 0.02
			self.level.health_bar.update(self.health)

		self.conductor.song_position += dt

		super().update(dt)
