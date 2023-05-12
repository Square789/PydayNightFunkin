
from enum import IntEnum
import random
import typing as t

from loguru import logger
from pyglet.math import Vec2

from pyday_night_funkin.base_game_pack import SongResourceOptions, load_song
from pyday_night_funkin.character import Character, CharacterData
from pyday_night_funkin.core.scene import BaseScene, SceneKernel
from pyday_night_funkin.core.utils import lerp
from pyday_night_funkin.enums import ANIMATION_TAG, CONTROL, DIFFICULTY
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.note import NOTE_TYPE, SUSTAIN_STAGE, Note
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.content_pack import LevelData
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class CharacterAnchor:
	__slots__ = ("position", "alignment", "layer", "cameras")

	def __init__(
		self,
		position: Vec2,
		alignment, # NOTE: Useless for now
		layer: t.Optional[t.Hashable] = None,
		cameras: t.Optional[t.Hashable] = None,
	) -> None:
		self.position = position
		self.alignment = alignment
		self.layer = layer
		self.cameras = cameras


class _ThrowawayGf(Character):
	"""
	A hidden character with no sprite that does nothing when `dance`
	is called. Used to hide girlfriend in levels where there is none.
	"""
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.visible = False

	def dance(self) -> None:
		pass


class GameState(IntEnum):
	LOADING = 0
	COUNTDOWN = 1
	PLAYING = 2
	ENDED = 3


class InGameSceneKernel(SceneKernel):
	def __init__(self, scene_type: t.Type["InGameScene"], *args, **kwargs) -> None:
		super().__init__(scene_type, *args, **kwargs)

		self.default_cam_zoom = None
		self.player_anchor = None
		self.girlfriend_anchor = None
		self.opponent_anchor = None

	def fill(
		self,
		*,
		default_cam_zoom: t.Optional[float] = None,
		player_anchor: t.Optional[CharacterAnchor] = None,
		girlfriend_anchor: t.Optional[CharacterAnchor] = None,
		opponent_anchor: t.Optional[CharacterAnchor] = None,
		**kwargs,
	):
		if self.default_cam_zoom is None:
			self.default_cam_zoom = default_cam_zoom
		if self.player_anchor is None:
			self.player_anchor = player_anchor
		if self.girlfriend_anchor is None:
			self.girlfriend_anchor = girlfriend_anchor
		if self.opponent_anchor is None:
			self.opponent_anchor = opponent_anchor

		super().fill(**kwargs)

		return self

	def create_scene(self, game: "Game") -> "InGameScene":
		scene = super().create_scene(game) # type: InGameScene
		scene.load_song()
		scene.ready()
		return scene


class InGameScene(scenes.MusicBeatScene):
	"""
	Main PNF game driver scene.
	Meant to be a jumble of sprites, players, handlers etc. running the
	entire game.
	Note that this base class only provides a small shred of
	functionality, for it to be playable it needs to be expanded
	by subclassing it (see existing weeks for examples).
	"""

	def __init__(
		self,
		kernel: InGameSceneKernel,
		level_data: "LevelData",
		difficulty: DIFFICULTY,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Optional[t.Sequence["LevelData"]] = None,
	) -> None:
		"""
		Initializes the InGame scene.

		:param kernel: The InGameSceneKernel to initialize the scene
		from.
		:param level_data: The level to be loaded. Heavily influences
		how the scene will play out.
		:param difficulty: Difficulty the scene plays in.
		:param follow_scene: Which scene type to push once the scene
		is over and `remaining_week` is exhausted or when the game is
		stopped otherwise by the user.
		:param remaining_week: A sequence of more `LevelData` to be
		turned into scenes that follow if the user wins this level.
		This runs the story mode and is additionally used to determine
		whether the story mode should be considered active at all.
		Freeplay/non-story mode is assumed when it's `None`.
		"""

		super().__init__(
			kernel.fill(
				default_cam_zoom = 1.05,
				cameras = ("main", "hud"),
			)
		)

		self.level_data = level_data
		self.difficulty = difficulty
		self.follow_scene = follow_scene
		"""The scene type that should be set once all songs are exhausted."""
		self.remaining_week = remaining_week
		self.in_story_mode = remaining_week is not None

		self._default_cam_zoom = kernel.default_cam_zoom

		self.player_anchor = kernel.player_anchor
		self.girlfriend_anchor = kernel.girlfriend_anchor
		self.opponent_anchor = kernel.opponent_anchor
		if any(a is None for a in (
			self.player_anchor, self.girlfriend_anchor, self.opponent_anchor
		)):
			logger.warning("A character anchor is None, expect an error!")

		self.draw_passthrough = False

		self.state = GameState.LOADING

		self.inst_player = self.game.sound.create_player()
		self.voice_player = self.game.sound.create_player()

		self.song_data: t.Optional[t.Dict] = None

		self.health: float = 0.5
		self.combo: int = 0
		self.score: int = 0

		self._last_followed_singer: int = 0
		"""
		An int indicating the character the camera is trained on.
		0 for the opponent, 1 for the player. Anything else is
		illegal.
		"""

		self.zoom_cams: bool = False

		self.gf_speed: int = 1
		"""
		Causes `self.girlfriend.dance` to be called on each xth beat.
		"""

		if self.game.player.playing:
			self.game.player.pause()

		self.boyfriend = self.create_character(self.player_anchor, level_data.player_character)
		if (gf_char_id := level_data.girlfriend_character) is None:
			# HACK: Feeding `CharacterData()` here is probably a gross violation of something
			self.girlfriend = self.create_object(
				"girlfriend", "main", _ThrowawayGf, self, CharacterData(_ThrowawayGf)
			)
		else:
			self.girlfriend = self.create_character(self.girlfriend_anchor, gf_char_id)
		self.opponent = self.create_character(self.opponent_anchor, level_data.opponent_character)

		self.main_cam = self.cameras["main"]
		self.hud_cam = self.cameras["hud"]

		self.note_handler = self.create_note_handler()

		self.hud = self.create_hud()
		self.hud.update_score(0)
		self.hud.update_health(0.5)

	@classmethod
	def get_kernel(
		cls,
		level_data: "LevelData",
		difficulty: DIFFICULTY,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Optional[t.Sequence["LevelData"]] = None,
	) -> InGameSceneKernel:
		return InGameSceneKernel(cls, level_data, difficulty, follow_scene, remaining_week)

	def create_note_handler(self) -> "AbstractNoteHandler":
		raise NotImplementedError("Subclass this!")

	def create_hud(self) -> "HUD":
		raise NotImplementedError("Subclass this!")

	def create_character(self, anchor: CharacterAnchor, char_id: t.Hashable) -> Character:
		# pos = self.scene_data.player_anchor
		# pos = self._POSITIONING_FUNCS[char_data.positioning.type](self, char_data)
		return self.game.character_registry.create_immediate(
			anchor.layer,
			anchor.cameras,
			char_id,
			self,
			x = anchor.position.x,
			y = anchor.position.y,
		)

	def load_song(self) -> t.Dict:
		"""
		# TODO doc
		"""
		inst, voices, song_data = load_song(
			self.level_data.song_name,
			SongResourceOptions(self.difficulty),
			cache = True,
		)

		self.pause_players()
		self.inst_player.next_source()
		self.inst_player.queue(inst)
		if voices is not None:
			self.voice_player.next_source()
			self.voice_player.queue(voices)

		self.conductor.bpm = song_data["bpm"]
		self.conductor.load_bpm_changes(song_data)
		self.note_handler.feed_song_data(song_data)

		self.song_data = song_data

	def ready(self) -> None:
		"""
		Called after `setup` and `load_song` have been called.
		Should be used to start the level.
		"""
		# NOTE: This is somewhat of a hack. In the original game, characters play
		# an animation when you create them, I don't feel like copying that so
		# they switch to their idle animation's first frame here.
		# This is actually required cause camera focussing subtly depends on that.
		# (Or maybe not so subtly, depends on the spritesheet.)
		# Yes, for FlipIdleCharacters, this means differrent behavior from the default
		# game. If you have complaints about that go send them to your nearest recycling bin.
		for c in (self.boyfriend, self.girlfriend, self.opponent):
			c.dance()

		self.main_cam.zoom = self._default_cam_zoom
		self.main_cam.look_at(self.opponent.get_midpoint())

		self._countdown_stage = 0
		self.state = GameState.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		self.sync_conductor_from_dt()
		self.clock.schedule_interval(
			self.countdown, self.conductor.beat_duration * 0.001
		)

	def resync(self) -> None:
		logger.info("Resyncing...")
		self.voice_player.pause()
		# NOTE: Conductor may be rewound here which has potential to screw things up real bad.
		new_pos = self.inst_player.time * 1000.0
		if new_pos < self.conductor.song_position:
			logger.warning(f"Rewound conductor by {self.conductor.song_position - new_pos}, oops.")
		self.conductor.song_position = new_pos
		self.voice_player.seek(self.conductor.song_position * 0.001)
		self.voice_player.play()

	def pause_players(self) -> None:
		"""
		Pauses the vocal and instrumental players.
		"""
		self.voice_player.pause()
		self.inst_player.pause()

	def play_players(self) -> None:
		"""
		Plays vocal and instrumental players.
		"""
		self.voice_player.play()
		self.inst_player.play()

	def start_song(self) -> None:
		"""
		Starts the song by making the players play, zeroing
		conductor's position and setting the state to PLAYING.
		This will also attach `self.on_song_end` to the inst player.
		"""
		self.conductor.song_position = 0
		self.sync_conductor_from_player(self.inst_player, True, False, False)
		self.inst_player.push_handlers(on_eos=self.on_song_end)
		self.play_players()
		self.state = GameState.PLAYING

	def get_current_section(self) -> t.Optional[t.Dict]:
		"""
		Returns the currently playing section of song data if song
		data exists and the conductor's song_position isn't out of
		bound, else `None`.
		"""
		if self.song_data is None:
			return None

		sec = self.cur_step // 16
		if sec < 0 or sec >= len(self.song_data["notes"]):
			return None

		return self.song_data["notes"][sec]

	def update(self, dt: float) -> None:
		super().update(dt)

		self.process_input(dt)
		if self.health < 0.0 and self.state is not GameState.ENDED:
			# Game over may have been triggered in process_input already
			self.on_game_over()

		# Camera following
		if (cur_section := self.get_current_section()) is not None:
			if (to_follow := int(cur_section["mustHitSection"])) != self._last_followed_singer:
				self._last_followed_singer = to_follow
				if to_follow == 0:
					_cam_follow = self.opponent.get_midpoint() + Vec2(150, -100)
				else:
					_cam_follow = self.boyfriend.get_midpoint() + Vec2(-100, -100)
				self.main_cam.set_follow_target(_cam_follow, 0.04)

		if self.zoom_cams:
			self.main_cam.zoom = lerp(self._default_cam_zoom, self.main_cam.zoom, 0.95)
			self.hud_cam.zoom = lerp(1.0, self.hud_cam.zoom, 0.95)

	def process_input(self, dt: float) -> None:
		"""
		Called with `update` every time.
		Keyboard input should be handled here.
		"""
		key_handler = self.game.key_handler
		pressed = {
			type_: key_handler.just_pressed(control)
			for type_, control in self.note_handler.NOTE_TO_CONTROL_MAP.items()
			if key_handler[control]
		}
		opponent_hit, player_missed, player_res = self.note_handler.update(pressed)

		if opponent_hit:
			op_note = opponent_hit[-1]
			self.opponent.hold_timer = 0.0
			self.opponent.animation.play(f"sing_{op_note.type.name.lower()}", True)
			self.zoom_cams = True

		if player_missed:
			for note in player_missed:
				self.on_note_miss(note)
			fail_note = player_missed[-1]
			self.boyfriend.animation.play(f"miss_{fail_note.type.name.lower()}", True)

		for type_ in NOTE_TYPE:
			if type_ not in player_res:
				# Note not being held, make the arrow static
				self.hud.arrow_static(type_)
			elif player_res[type_] is None:
				# Note was pressed but player missed
				self.hud.arrow_pressed(type_)
				if pressed[type_]: # Just pressed
					self.on_misinput(type_)
			else:
				# Note was pressed and player hit
				self.hud.arrow_confirm(type_)
				self.on_note_hit(player_res[type_])
				# TODO extract to on_note_hit etc, rework this yada yada
				self.score += 100
				self.hud.update_score(self.score)

		self.boyfriend.dont_idle = bool(pressed)

		handler_called = False
		if self.game.debug:
			if key_handler.just_pressed(CONTROL.DEBUG_DESYNC):
				desync = random.randint(-400, 400)
				logger.debug(f"Desyncing conductor by {desync}ms")
				self.conductor.song_position += desync
			if key_handler.just_pressed(CONTROL.DEBUG_WIN):
				handler_called = True
				self.on_song_end()
			if key_handler.just_pressed(CONTROL.DEBUG_LOSE) and not handler_called:
				handler_called = True
				self.on_game_over()

		if key_handler.just_pressed(CONTROL.ENTER) and not handler_called:
			handler_called = True
			self.on_pause()

	def on_note_hit(self, note: Note) -> None:
		"""
		Called whenever a note is hit.
		By default, causes BF to play an appropiate animation, causes
		combo popups and adjusts health.
		"""
		self.boyfriend.hold_timer = 0.0
		self.boyfriend.animation.play(f"sing_{note.type.name.lower()}", True)

		health = 0.004
		if note.sustain_stage is SUSTAIN_STAGE.NONE:
			self.combo += 1
			self.hud.combo_popup(note.rating, self.combo)
			health = 0.023

		self.set_health(self.health + health)

	def on_note_miss(self, note: Note) -> None:
		"""
		Called whenever a note is missed by it going offscreen.
		By default, reduces health.
		"""
		self.set_health(self.health - 0.0475)

	def on_misinput(self, type_: NOTE_TYPE) -> None: # CALM DOWN CALM DOWN
		"""
		Called whenever an arrow is pressed and no note for it was
		playable.
		By default, plays a miss animation on bf, breaks the combo and
		reduces health.
		"""
		self.boyfriend.animation.play(f"miss_{type_.name.lower()}", True)
		self.combo = 0
		self.set_health(self.health - 0.04)

	def set_health(self, new_health: float) -> None:
		"""
		Sets health of the player to the specified new health and
		then calls everything that should necessarily update.
		"""
		self.health = min(new_health, 1.0)
		self.hud.update_health(new_health)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if self.zoom_cams and self.main_cam.zoom < 1.35 and self.cur_beat % 4 == 0:
			self.main_cam.zoom += 0.015
			self.hud_cam.zoom += 0.03

		if self.cur_beat % self.gf_speed == 0:
			self.girlfriend.dance()

		if self.cur_beat % 2 == 0:
			# This code's purpose should be to get bf out of special animations such as
			# the bopeebo v-signs
			t = self.boyfriend.animation.current.tags
			if not (ANIMATION_TAG.MISS in t or ANIMATION_TAG.SING in t):
				self.boyfriend.dance()

			if not self.opponent.animation.has_tag(ANIMATION_TAG.SING):
				self.opponent.dance()

	def on_pause(self) -> None:
		"""
		Called when user requested to open the pause menu.
		Stops the song players and opens the pause menu.
		"""
		self.pause_players()
		self.game.push_scene(scenes.PauseScene)

	def on_song_end(self) -> None:
		"""
		Song has ended. Default implementation sets the game's state
		to `ENDED` and returns to the previous scene, unless more
		`InGameScene`s are in `self.remaining_week`, in which case they
		are created with this scene's difficulty and follow scene.
		"""
		self.pause_players()
		self.state = GameState.ENDED
		if self.remaining_week:
			next_level_data, *week_rest = self.remaining_week
			self.game.set_scene(
				next_level_data.stage_type.get_kernel(
					next_level_data, self.difficulty, self.follow_scene, week_rest
				)
			)
			return
		else:
			self.game.set_scene(self.follow_scene)

	def on_game_over(self) -> None:
		"""
		Called when the player failed and caused the game to end,
		probably by running out of health.
		Sets the game state to `ENDED` and pushes a `GameOverScene`.
		"""
		self.pause_players()
		self.state = GameState.ENDED

		if self.boyfriend.character_data.game_over_fallback is not None:
			cd = self.game.character_registry[self.boyfriend.character_data.game_over_fallback]
			game_over_bf = cd.type(self, cd)
		else:
			# Definitely do not want to add him to two scenes
			game_over_bf = self.boyfriend
			self.remove(game_over_bf, keep=True)

		game_over_bf.position = tuple(self.boyfriend.get_screen_position(self.main_cam))
		self.game.push_scene(scenes.GameOverScene.get_kernel(game_over_bf))

	def countdown(self, dt: float) -> None:
		self.opponent.dance()
		self.girlfriend.dance()
		self.boyfriend.dance()

		if self._countdown_stage == 4:
			self.start_song()
			self.clock.unschedule(self.countdown)
		else:
			# self._countdown_stage will be changed once hide is called
			self.hud.countdown_popup(self._countdown_stage)
			self._countdown_stage += 1

	def on_subscene_removal(self, subscene, end_self=None, reset=False) -> None:
		super().on_subscene_removal(subscene)
		if end_self is None:
			return

		if end_self:
			self.game.set_scene(self.follow_scene)
		else:
			if not reset:
				if self.state is GameState.PLAYING:
					self.play_players()
					self.resync()
			else:
				self.game.set_scene(
					self.level_data.stage_type.get_kernel(
						self.level_data,
						self.difficulty,
						self.follow_scene,
						self.remaining_week,
					)
				)

	def destroy(self) -> None:
		super().destroy()
		self.voice_player.destroy()
		self.inst_player.destroy()
		# Pathetic attempt at cleaning up more cyclic references i guess
		del self.note_handler
		del self.boyfriend
		del self.girlfriend
		del self.opponent
