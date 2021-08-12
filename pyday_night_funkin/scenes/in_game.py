
from dataclasses import dataclass
from enum import IntEnum
from loguru import logger
import math
import typing as t

from pyglet.media import Player
from pyglet.media.player import PlayerGroup

from pyday_night_funkin.asset_system import ASSETS
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.config import KEY
from pyday_night_funkin.note import NOTE_TYPE, SUSTAIN_STAGE, Note
from pyday_night_funkin.scenes._base import BaseScene
from pyday_night_funkin.utils import ListWindow

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
		self.paused = False

		self._notes: t.List[Note] = []
		# Notes that are in the view area of the game, not neccessairly visible since they
		# may have been played.
		self._visible_notes = ListWindow(self._notes, 0, 0)
		self._playable_notes = ListWindow(self._notes, 0, 0)
		note_assets = ASSETS.XML.NOTES.load()
		self.note_sprites = {
			SUSTAIN_STAGE.NONE: {
				NOTE_TYPE.LEFT: note_assets["purple"][0],
				NOTE_TYPE.DOWN: note_assets["blue"][0],
				NOTE_TYPE.UP: note_assets["green"][0],
				NOTE_TYPE.RIGHT: note_assets["red"][0],
			},
			SUSTAIN_STAGE.TRAIL: {
				NOTE_TYPE.LEFT: note_assets["purple hold piece"][0],
				NOTE_TYPE.DOWN: note_assets["blue hold piece"][0],
				NOTE_TYPE.UP: note_assets["green hold piece"][0],
				NOTE_TYPE.RIGHT: note_assets["red hold piece"][0],
			},
			SUSTAIN_STAGE.END: {
				# this is the worst naming of anything i have ever seen
				NOTE_TYPE.LEFT: note_assets["pruple end hold"][0],
				NOTE_TYPE.DOWN: note_assets["blue hold end"][0],
				NOTE_TYPE.UP: note_assets["green hold end"][0],
				NOTE_TYPE.RIGHT: note_assets["red hold end"][0],
			},
		}
		self.song_data = None
		self.scroll_speed = self.game.config.scroll_speed
		self.conductor = Conductor()
		self._updates_since_desync_warn = 999
		self._setup_song()
		self.health = 0.5

		self.level.load_resources()
		self.level.on_start()
		self.cameras["main"].y += 200

	def _setup_song(self) -> None:
		"""
		Queues the two song sources (out of which the second one may
		be None) as returned by `load_song` in the players, configures
		the conductor with the song's metadata and creates all notes.
		"""
		inst, voices, song_data = self.level.load_song()
		self.song_players.pause()
		self.inst_player.next_source()
		self.inst_player.queue(inst)
		if voices is not None:
			self.voice_player.next_source()
			self.voice_player.queue(voices)

		self.song_data = song_data
		self.scroll_speed *= song_data["song"]["speed"]
		self.conductor.bpm = song_data["song"]["bpm"]
		for section in song_data["song"]["notes"]:
			for time_, type_, sustain in section["sectionNotes"]:
				singer = int(section["mustHitSection"]) # 0: opponent, 1: bf
				if type_ >= len(NOTE_TYPE): # Note is sung by other character
					type_ %= len(NOTE_TYPE)
					singer ^= 1
				type_ = NOTE_TYPE(type_)
				note = Note(singer, time_, type_, sustain, SUSTAIN_STAGE.NONE)
				self._notes.append(note)
				trail_notes = math.ceil(sustain / self.conductor.beat_step_duration)
				for i in range(trail_notes): # 0 and effectless for non-sustain notes.
					sust_time = time_ + (self.conductor.beat_step_duration * (i + 1))
					stage = SUSTAIN_STAGE.END if i == trail_notes - 1 else SUSTAIN_STAGE.TRAIL
					sust_note = Note(singer, sust_time, type_, sustain, stage)
					self._notes.append(sust_note)
		self._notes.sort()

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
			self.conductor.song_position += dt * 1000
			# discrepancy = self.inst_player.time * 1000 - self.conductor.song_position
			# if abs(discrepancy) > 20 and self._updates_since_desync_warn > 100:
			# 	logger.warning(f"Conductor out of sync with player by {discrepancy:.4f} ms.")
			# 	self._updates_since_desync_warn = 0
			# self._updates_since_desync_warn += 1
			self._update_notes()

		self._handle_keys()

		if self.state != IN_GAME_STATE.LOADING:
			self._update_animations()

		super().update(dt)

	def _update_animations(self) -> None:
		pass

	def _update_notes(self) -> None:
		"""
		Spawns, draws and deletes notes on screen.
		Additionally, manages the visible and playable windows.
		"""
		# NOTE: Could create methods on the ListWindow to eliminate
		# "grow, update-shrink" code duplication
		# Pixels a note traverses in a millisecond
		speed = 0.45 * self.scroll_speed
		note_vis_window_time = (CNST.GAME_HEIGHT - CNST.STATIC_ARROW_Y) / speed
		# NOTE: Makes assumption they're all the same (spoilers: they are)
		arrow_width = self.note_sprites[SUSTAIN_STAGE.NONE][NOTE_TYPE.UP].texture.width * 0.7
		
		# Checks for notes that entered the visibility window, creates their sprites.
		while (
			self._visible_notes.end < len(self._notes) and
			self._notes[self._visible_notes.end].time - self.conductor.song_position \
				<= note_vis_window_time
		):
			cur_note = self._notes[self._visible_notes.end]
			x = 50 + (CNST.GAME_WIDTH // 2) * cur_note.singer + \
				cur_note.type.get_order() * arrow_width
			# No i am not calling it sus_stage
			sust_stage = cur_note.sustain_stage
			texture = self.note_sprites[sust_stage][cur_note.type].texture
			sprite = self.create_sprite("ui1", (x, -2000), texture, "ui")
			sprite.world_scale = 0.7
			if sust_stage != SUSTAIN_STAGE.NONE:
				sprite.world_x += (arrow_width - texture.width) // 2
				if sust_stage == SUSTAIN_STAGE.TRAIL:
					sprite.world_scale_y = self.conductor.beat_step_duration * 0.015 * \
						self.scroll_speed
			cur_note.sprite = sprite
			self._visible_notes.end += 1

		# Updates and shrinks visible notes window, makes played notes invisible,
		# deletes off-screen ones.
		for note in self._visible_notes:
			note_y = CNST.STATIC_ARROW_Y - (self.conductor.song_position - note.time) * speed
			if note_y < -note.sprite.height:
				self._visible_notes.start += 1
				self.remove_sprite(note.sprite)
				note.sprite.delete()
				note.sprite = None
			elif note.hit_state is not None:
				note.sprite.visible = False
			else:
				note.sprite.world_y = note_y

		# Finds new playable notes
		while (
			self._playable_notes.end < len(self._notes) and
			self._notes[self._playable_notes.end].is_playable(
				self.conductor.song_position,
				self.game.config.safe_window,
			)
		):
			self._playable_notes.end += 1

		# Updates playable notes and shrinks playable notes window by removing missed notes.
		for note in self._playable_notes:
			note.check_playability(
				self.conductor.song_position,
				self.game.config.safe_window,
			)
			if note.missed:
				self._playable_notes.start += 1

	def _handle_keys(self) -> None:
		if (
			self.state != IN_GAME_STATE.COUNTDOWN and
			self.state != IN_GAME_STATE.PLAYING
		):
			return

		pressed: t.Dict[NOTE_TYPE, t.Optional[Note]] = {}
		just_pressed: t.Dict[NOTE_TYPE, bool] = {}
		for note_type, key in zip(
			(NOTE_TYPE.LEFT, NOTE_TYPE.DOWN, NOTE_TYPE.UP, NOTE_TYPE.RIGHT),
			(KEY.LEFT, KEY.DOWN, KEY.UP, KEY.RIGHT)
		):
			if self.game.key_handler[key]:
				pressed[note_type] = None
				just_pressed[note_type] = self.game.key_handler.just_pressed(key)

		for note in self._playable_notes:
			if note.singer != 1 or note.hit_state is not None or note.type not in pressed:
				continue
			if note.type in pressed:
				pressed[note.type] = note

		for note_type in NOTE_TYPE:
			if note_type not in pressed:
				if self.level.static_arrows[1][note_type].current_animation != "static":
					self.level.static_arrows[1][note_type].play_animation("static")
			else:
				if pressed[note_type] is None:
					if (
						self.level.static_arrows[1][note_type].current_animation is not None and
						self.level.static_arrows[1][note_type].current_animation == "static"
					):
						self.level.static_arrows[1][note_type].play_animation("pressed")
						self.level.bf.play_animation(f"note_{note_type.name.lower()}_miss")
				else:
					if (
						(pressed[note_type].sustain_stage == SUSTAIN_STAGE.NONE and just_pressed[note_type]) or
						(pressed[note_type].sustain_stage != SUSTAIN_STAGE.NONE)
					):
						pressed[note_type].on_hit()
						self.level.bf.play_animation(f"note_{note_type.name.lower()}")
						self.level.static_arrows[1][note_type].play_animation("confirm")
