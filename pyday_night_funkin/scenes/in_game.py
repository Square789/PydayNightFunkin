
from dataclasses import dataclass
from enum import IntEnum
import typing as t
from loguru import logger

from pyglet.media import Player
from pyglet.media.player import PlayerGroup
from pyglet.window import key

from pyday_night_funkin.asset_system import ASSETS
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.note import NOTE_TYPE, Note
from pyday_night_funkin.scenes._base import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.levels import Week


@dataclass
class InGameInfo():
	difficulty: CNST.DIFFICULTY


class IN_GAME_STATE(IntEnum):
	LOADING = 0
	START_DIALOGUE = 1
	COUNTDOWN = 2
	PLAYING = 3
	END_DIALOGUE = 4


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
		self.state = IN_GAME_STATE.LOADING

		self._last_created_note = -1
		self._visible_notes: t.List[Note] = []
		self._notes: t.List[Note] = []
		note_assets = ASSETS.XML.NOTES.load()
		self.note_sprites = {
			NOTE_TYPE.LEFT: note_assets["purple"][0],
			NOTE_TYPE.DOWN: note_assets["blue"][0],
			NOTE_TYPE.UP: note_assets["green"][0],
			NOTE_TYPE.RIGHT: note_assets["red"][0],
		}
		self.song_data = None
		self.scroll_speed = self.game.config.scroll_speed
		self.conductor = Conductor()
		self._warned_about_conductor_desync = False
		self._setup_song()
		self.health = 0.5

		self.level.load_resources()
		self.level.on_start()

	def _setup_song(self) -> None:
		"""
		Queues the two song sources (out of which the second one may
		be None) as returned by `load_song` in the players and
		configures the conductor with the song's metadata.
		"""
		inst, voices, song_data = self.level.load_song()
		self.song_players.pause()
		self.inst_player.next_source()
		self.inst_player.queue(inst)
		if voices is not None:
			self.voice_player.next_source()
			self.voice_player.queue(voices)

		self.song_data = song_data
		for section in song_data["song"]["notes"]:
			singer = int(section["mustHitSection"]) # 0: opponent, 1: bf
			for time_, type_, sustain in section["sectionNotes"]:
				if type_ >= len(NOTE_TYPE): # Note is sung by other character
					type_ %= len(NOTE_TYPE)
					singer ^= 1
				self._notes.append(Note(singer, time_ / 1000, NOTE_TYPE(type_), sustain))
		self._notes.sort()
		self.scroll_speed *= song_data["song"]["speed"]
		self.conductor.bpm = song_data["song"]["bpm"]

	def start_song(self) -> None:
		"""
		Starts the song by making the players play, zeroing
		conductor's position and setting the scene's state to PLAYING.
		"""
		logger.debug(f"Started song! Scroll speed: {self.scroll_speed}")
		self.state = IN_GAME_STATE.PLAYING
		self.conductor.song_position = 0
		self.song_players.play()

	def update(self, dt: float) -> None:
		if self.state == IN_GAME_STATE.COUNTDOWN or self.state == IN_GAME_STATE.PLAYING:
			self.conductor.song_position += dt
			discrepancy = self.inst_player.time - self.conductor.song_position
			if abs(discrepancy) > .05 and not self._warned_about_conductor_desync:
				logger.warning(f"Conductor out of sync with player by {discrepancy:.4f} s.")
				self._warned_about_conductor_desync = True
			self._update_notes()

		super().update(dt)

	def _update_notes(self) -> None:
		"""
		Spawns, draws and deletes notes on screen.
		"""
		# Pixels a note traverses in a second
		speed = 450 * self.scroll_speed
		note_vis_window_time = ((CNST.GAME_HEIGHT - CNST.STATIC_ARROW_Y) / speed)
		# Check for notes that entered the visibility window
		if self._last_created_note < len(self._notes) - 1:
			cur_note = self._notes[self._last_created_note + 1]
			while True:
				if (cur_note.time - self.conductor.song_position) > note_vis_window_time:
					break
				x = 50 + (CNST.GAME_WIDTH // 2) * cur_note.singer + (
					cur_note.type.get_order() *
					self.note_sprites[cur_note.type].texture.width * .7
				)
				cur_note.sprite = self.create_sprite(
					"ui1", (x, -2000), self.note_sprites[cur_note.type].texture, "ui"
				)
				cur_note.sprite.world_scale = 0.7
				self._visible_notes.append(cur_note)
				self._last_created_note += 1
				if self._last_created_note < len(self._notes) - 1:
					cur_note = self._notes[self._last_created_note + 1]
				else:
					break

		despawned_notes = []
		for note in self._visible_notes:
			note_y = CNST.STATIC_ARROW_Y - (self.conductor.song_position - note.time) * speed
			if note_y < -note.sprite._texture.width:
				despawned_notes.append(note)
			else:
				note.sprite.world_y = note_y

		for note in despawned_notes:
			self._visible_notes.remove(note) # O(n**2), yuck
			self.remove_sprite(note.sprite)
			note.sprite.delete()
			note.sprite = None
