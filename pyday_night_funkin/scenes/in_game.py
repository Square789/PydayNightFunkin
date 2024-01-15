
from collections import defaultdict
from enum import IntEnum
import random
import typing as t

from loguru import logger
from pyglet.math import Vec2

from pyday_night_funkin.base_game_pack import fetch_song
from pyday_night_funkin.character import Character, CharacterData
from pyday_night_funkin.core.scene import BaseScene, SceneKernel, BaseSceneArgDict
from pyday_night_funkin.core.utils import lerp
from pyday_night_funkin.enums import AnimationTag, Control, Difficulty
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.note import NoteType, SustainStage, Note
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.content_pack import LevelData
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class AnchorAlignment:
	BOTTOM_LEFT =  Vec2( 0, -1)
	BOTTOM_RIGHT = Vec2(-1, -1)
	TOP_LEFT =     Vec2( 0,  0)
	TOP_RIGHT =    Vec2(-1,  0)


class Anchor:
	__slots__ = ("position", "alignment", "layer", "cameras")

	def __init__(
		self,
		position: Vec2,
		alignment: t.Optional[Vec2] = None,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
	) -> None:
		self.position = position
		self.alignment = AnchorAlignment.TOP_LEFT if alignment is None else alignment
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


class _Dancer(t.Protocol):
	def dance(self) -> t.Any:
		...


class DancerInfo:
	__slots__ = ("frequency", "offset", "during_countdown")

	def __init__(self, frequency: int = 1, offset: int = 0, during_countdown: bool = True) -> None:
		"""
		Initializes a `DancerInfo` helper class.
		:param frequency: How frequently to dance. 1 will do it every
		beat, 2 every two beats, etc.
		:param offset: On which beat to dance. For `frequency` 2,
		setting this value to 1 will cause the `dance` method to be
		called only on odd beats.
		:param during_countdown: Whether to dance during the countdown
		steps as well.
		"""
		self.frequency = frequency
		self.offset = offset
		self.during_countdown = during_countdown


class FocusTargetInfo:
	__slots__ = ("character", "additional_offset")

	def __init__(self, character: Character, additional_offset: t.Optional[Vec2] = None) -> None:
		self.character = character
		self.additional_offset = Vec2(0.0, 0.0) if additional_offset is None else additional_offset

	def get_focus_point(self) -> Vec2:
		return self.character.get_focus_point() + self.additional_offset


class GameState(IntEnum):
	LOADING = 0
	COUNTDOWN = 1
	PLAYING = 2
	ENDED = 3


class _InGameSceneArgDict(BaseSceneArgDict, total=False):
	default_cam_zoom: t.Optional[float]
	player_anchor: t.Optional[Anchor]
	girlfriend_anchor: t.Optional[Anchor]
	opponent_anchor: t.Optional[Anchor]


class InGameSceneKernel(SceneKernel):
	def __init__(
		self,
		scene_type: t.Type["InGameScene"],
		level_data: "LevelData",
		difficulty: Difficulty,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Optional[t.Sequence["LevelData"]] = None,
	) -> None:
		super().__init__(scene_type, level_data, difficulty, follow_scene, remaining_week)

		self._level_data = level_data
		self._difficulty = difficulty
		self._remaining_week = remaining_week

		self.default_cam_zoom: t.Optional[float] = None
		self.player_anchor: t.Optional[Anchor] = None
		self.girlfriend_anchor: t.Optional[Anchor] = None
		self.opponent_anchor: t.Optional[Anchor] = None

		self.register_kernel_params(
			"default_cam_zoom", "player_anchor", "girlfriend_anchor", "opponent_anchor"
		)

	def get_loading_hints(self) -> ...:
		"""
		Generates asset requests for a typical InGameScene.
		This duplicates some code to load a level's character's
		spritesheets as well as the song, nothing else.
		"""
		from pyday_night_funkin.core.asset_system import AssetRequest, LoadingRequest, load_pyobj

		# TODO: Load songs/characters of an entire week

		def _on_song_data_load(json_data):
			song_dir = load_pyobj("PATH_SONGS") / self._level_data.song_name

			return_hits = {"sound": [AssetRequest((song_dir / "Inst.ogg",))]}
			if json_data["needsVoices"]:
				return_hits["sound"].append(AssetRequest((song_dir / "Voices.ogg",),))

			return LoadingRequest(return_hits)

		# TODO: Make adjustments to characters so this method can request loading of
		# their spritesheets.
		# Also, get_loading_hints should probably take game as a parameter
		# Or maybe kernels should just get it at initialization unconditionally.
		# So much to do so much to see so much to do so much to see

		return LoadingRequest(
			{
				"_pnf_song_data": (
					AssetRequest(
						(self._level_data.song_name, self._difficulty),
						completion_tag = "song_data.0",
					),
				),
			},
			{"song_data": _on_song_data_load},
			self._level_data.libraries or [],
		)

	def fill(self, arg_dict: t.Optional[_InGameSceneArgDict] = None, **kwargs):
		return super().fill(arg_dict, **kwargs)

	def create_scene(self, game: "Game") -> "InGameScene":
		scene = super().create_scene(game) # type: InGameScene
		scene.load_song()
		scene.ready()
		return scene


class InGameScene(scenes.MusicBeatScene):
	"""
	The main PNF ingame driver scene.
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
		difficulty: Difficulty,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Optional[t.Sequence["LevelData"]] = None,
	) -> None:
		"""Initializes the InGame scene."""

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

		self.draw_passthrough = False

		self.allow_pausing = True
		"""
		Whether the InGameScene should open a pause menu if the
		user hits the pause key.
		"""

		self.state = GameState.LOADING

		self.inst_player = self.game.sound.create_player()
		self.voice_player = self.game.sound.create_player()

		self.song_data: t.Optional[t.Dict] = None

		self.health: float = 0.5
		self.combo: int = 0
		self.score: int = 0

		self._last_focused_character: int = 0
		"""
		An int indicating the character the camera is trained on.
		0 for the opponent, 1 for the player. Anything else is
		illegal.
		"""

		self.focus_targets: t.List[FocusTargetInfo] = []
		"""
		Stuff that can be focussed by cameras. Realistically, just a
		2-element list connected to `self._last_focused_character`,
		where 0 is the opponent and 1 is the player character.
		"""

		self.zoom_cams: bool = False

		self.dancers: t.DefaultDict[_Dancer, DancerInfo] = defaultdict(DancerInfo)
		"""
		Stuff that dances. This includes just about anything that
		has a `dance` method, which will be called by the InGameScene
		every time a beat is hit; or by the countdown phase as well if
		applicable.
		"""

		if self.game.player.playing:
			self.game.player.pause()

		self.boyfriend = self.create_character(
			self.player_anchor, level_data.player_character
		)
		if (gf_char_id := level_data.girlfriend_character) is None:
			# HACK: Feeding `CharacterData()` here is probably a gross violation of something
			self.girlfriend = self.create_object(
				"girlfriend", "main", _ThrowawayGf, self, CharacterData(_ThrowawayGf)
			)
		else:
			self.girlfriend = self.create_character(self.girlfriend_anchor, gf_char_id)
		self.opponent = self.create_character(
			self.opponent_anchor, level_data.opponent_character
		)

		self.dancers[self.opponent] = DancerInfo(2, 0)
		self.dancers[self.boyfriend] = DancerInfo(2, 0)
		self.dancers[self.girlfriend] = DancerInfo(1, 0)

		self.focus_targets.append(FocusTargetInfo(self.opponent))
		self.focus_targets.append(FocusTargetInfo(self.boyfriend))

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
		difficulty: Difficulty,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Optional[t.Sequence["LevelData"]] = None,
	) -> InGameSceneKernel:
		"""
		Creates a kernel suitable to pass to an InGameScene (or
		subclass thereof) when it's time to actually create it.

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
		return InGameSceneKernel(cls, level_data, difficulty, follow_scene, remaining_week)

	def create_note_handler(self) -> "AbstractNoteHandler":
		raise NotImplementedError("Subclass this!")

	def create_hud(self) -> "HUD":
		raise NotImplementedError("Subclass this!")

	def create_character(self, anchor: Anchor, char_id: t.Hashable) -> Character:
		data = self.game.character_registry[char_id]
		char = self.create_object(anchor.layer, anchor.cameras, data.type, self, data)
		char.position = (
			anchor.position.x + char.width * anchor.alignment.x,
			anchor.position.y + char.height * anchor.alignment.y,
		)
		# print(
		# 	f"Created character {char.character_data.type} @ {char.position}. "
		# 	f"Spans {char.width}, {char.height}"
		# )
		return char

	def load_song(self) -> None:
		"""
		# TODO doc
		"""
		inst, voices, song_data = fetch_song(self.level_data.song_name, self.difficulty)

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
		Starts the level by setting the main camera's zoom as well as
		view targets and initializing the countdown.
		"""
		# NOTE: Typically, characters play an animation when you create them, which then goes on
		# to subtly influence camera focussing.
		# (Or maybe not so subtly, depends on the spritesheet.)
		self.main_cam.zoom = self._default_cam_zoom
		self.main_cam.look_at(
			self.opponent.get_current_frame_dimensions() * 0.5 +
			Vec2(100.0, 100.0)
		)

		if self.song_data["notes"]:
			self._set_focused_character(int(self.song_data["notes"][0]["mustHitSection"]))

		self._countdown_stage = 0
		self.state = GameState.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		self.sync_conductor_from_dt()
		self.clock.schedule_interval(self.countdown, self.conductor.beat_duration * 0.001)

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

	def _set_focused_character(self, focus_target: int) -> None:
		self._last_focused_character = focus_target
		target = self.focus_targets[focus_target]
		self.main_cam.set_follow_target(target.get_focus_point(), 0.04)

	def update(self, dt: float) -> None:
		super().update(dt)

		self.process_input(dt)
		if self.health < 0.0 and self.state is not GameState.ENDED:
			# Game over may have been triggered in process_input already
			self.on_game_over()

		# Camera following
		if (cur_section := self.get_current_section()) is not None:
			if (to_follow := int(cur_section["mustHitSection"])) != self._last_focused_character:
				self._set_focused_character(to_follow)

		if self.zoom_cams:
			# NOTE: Hardcoded FPS of 60
			self.main_cam.zoom = lerp(self._default_cam_zoom, self.main_cam.zoom, 0.95 * 60.0 * dt)
			self.hud_cam.zoom = lerp(1.0, self.hud_cam.zoom, 0.95 * 60.0 * dt)

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

		for type_ in NoteType:
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
			if key_handler.just_pressed(Control.DEBUG_DESYNC):
				desync = random.randint(-400, 400)
				logger.debug(f"Desyncing conductor by {desync}ms")
				self.conductor.song_position += desync
			if key_handler.just_pressed(Control.DEBUG_WIN):
				handler_called = True
				self.on_song_end()
			if key_handler.just_pressed(Control.DEBUG_LOSE) and not handler_called:
				handler_called = True
				self.on_game_over()

		if key_handler.just_pressed(Control.ENTER) and not handler_called:
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
		if note.sustain_stage is SustainStage.NONE:
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

	def on_misinput(self, type_: NoteType) -> None: # CALM DOWN CALM DOWN
		"""
		Called whenever an arrow is pressed and no note for it was
		playable.
		By default, plays a miss animation on bf, breaks the combo and
		reduces health.
		"""
		self.boyfriend.animation.play(f"miss_{type_.name.lower()}", True)
		if self.combo > 5 and self.girlfriend.animation.exists("sad"):
			self.girlfriend.animation.play("sad")

		self.combo = 0
		self.set_health(self.health - 0.04)

	def set_health(self, new_health: float) -> None:
		"""
		Sets health of the player to the specified new health and
		then calls everything that should necessarily update.
		"""
		self.health = min(new_health, 1.0)
		self.hud.update_health(new_health)

	def countdown(self, _dt: float) -> None:
		if self._countdown_stage >= 4:
			self.start_song()
			self.clock.unschedule(self.countdown)
			return

		self.hud.countdown_popup(self._countdown_stage)

		for dancer, info in self.dancers.items():
			if info.during_countdown and (self._countdown_stage % info.frequency == info.offset):
				dancer.dance()

		self._countdown_stage += 1

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if self.zoom_cams and self.main_cam.zoom < 1.35 and self.cur_beat % 4 == 0:
			self.main_cam.zoom += 0.015
			self.hud_cam.zoom += 0.03

		for dancer, info in self.dancers.items():
			if self.cur_beat % info.frequency == info.offset:
				dancer.dance()

	def on_pause(self) -> None:
		"""
		Called when user requested to open the pause menu.
		Stops the song players and opens the pause menu, as long as
		it's allowed per `allow_pausing`.
		"""
		if self.allow_pausing:
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

		# Do not transition out anymore once the gameover scene has been opened cause the
		# glimpse of a bf-less dead stage is weird
		self.skip_transition_out = True

		self.game.push_scene(scenes.GameOverScene.get_kernel(game_over_bf))

	def on_subscene_removal(self, subscene, end_game=None, reset=False, *_, **__) -> None:
		super().on_subscene_removal(subscene)
		if end_game is None:
			return

		if end_game:
			self.state = GameState.ENDED
			self.allow_pausing = False
			# It's possible to end the game while countdown is running, which will start the game
			# again during the out transition. Inhibit that here.
			self.clock.unschedule(self.countdown)
			self.game.set_scene(self.follow_scene)
		else:
			if reset:
				self.allow_pausing = False
				self.game.set_scene(
					self.get_kernel(
						self.level_data, self.difficulty, self.follow_scene, self.remaining_week
					)
				)
			else:
				if self.state is GameState.PLAYING:
					self.play_players()
					self.resync()

	def destroy(self) -> None:
		super().destroy()
		self.voice_player.destroy()
		self.inst_player.destroy()
		# Pathetic attempt at cleaning up more cyclic references i guess
		del self.dancers
		del self.note_handler
		del self.boyfriend
		del self.girlfriend
		del self.opponent
