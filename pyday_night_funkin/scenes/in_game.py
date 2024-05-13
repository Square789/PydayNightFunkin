
from collections import defaultdict
from enum import IntEnum
import random
import typing as t

from loguru import logger
from pyglet.math import Vec2

from pyday_night_funkin.base_game_pack import fetch_song
from pyday_night_funkin.character import Character, CharacterData
from pyday_night_funkin.core.asset_system import AssetRequest, LoadingRequest, load_pyobj
from pyday_night_funkin.core.scene import BaseScene, SceneKernel, BaseSceneArgDict
from pyday_night_funkin.core.utils import lerp
from pyday_night_funkin.enums import Control, Difficulty
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.note import NoteType, SustainStage, Note
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.content_pack import LevelData
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.scene_container import SceneLayer
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class AnchorAlignment:
	BOTTOM_LEFT =  Vec2( 0, -1)
	BOTTOM_RIGHT = Vec2(-1, -1)
	TOP_LEFT =     Vec2( 0,  0)
	TOP_RIGHT =    Vec2(-1,  0)


class Anchor:
	__slots__ = ("position", "alignment")

	def __init__(
		self,
		position: Vec2,
		alignment: t.Optional[Vec2] = None,
	) -> None:
		self.position = position
		self.alignment = AnchorAlignment.TOP_LEFT if alignment is None else alignment


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
		game: "Game",
		level_data: "LevelData",
		difficulty: Difficulty,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Optional[t.Sequence["LevelData"]] = None,
	) -> None:
		super().__init__(scene_type, game, level_data, difficulty, follow_scene, remaining_week)

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

	def get_loading_hints(self, game: "Game") -> "LoadingRequest":
		"""
		Generates asset requests for a typical InGameScene.
		Duplicates some code to load the level's song's assets.
		"""
		# TODO: Load songs/characters of an entire week?

		char_lreq = LoadingRequest({})
		for char_id in (
			self._level_data.player_character,
			self._level_data.girlfriend_character,
			self._level_data.opponent_character,
		):
			if char_id is None:
				continue

			char_lreq.add_subrequest(self.game.character_registry[char_id].get_loading_hints(game))

		def _on_song_data_load(json_data: t.Dict) -> LoadingRequest:
			song_dir = load_pyobj("PATH_SONGS") / self._level_data.song_name

			return_hits = {"sound": [AssetRequest((song_dir / "Inst.ogg",))]}
			if json_data["needsVoices"]:
				return_hits["sound"].append(AssetRequest((song_dir / "Voices.ogg",),))

			return LoadingRequest(return_hits)

		req = LoadingRequest(
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

		req.add_subrequest(char_lreq)

		return req

	def fill(self, arg_dict: t.Optional[_InGameSceneArgDict] = None, **kwargs):
		return super().fill(arg_dict, **kwargs)

	def create_scene(self) -> "InGameScene":
		scene = super().create_scene() # type: InGameScene
		scene.init_basic_fnf_stuff()
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
			)
		)

		self.main_cam = self.create_camera()
		self.hud_cam = self.create_camera()

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

		self.do_focus = True
		"""
		Whether to focus the cameras on targets.
		Useful to disable when you want to play a cutscene or something.

		This doesn't stop the camera itself from moving around, but
		does stop any ``InGameScene``'s methods from setting a focus target.
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

		self.boyfriend: t.Optional[Character] = None
		self.girlfriend: t.Optional[Character] = None
		self.opponent: t.Optional[Character] = None

		self.note_handler: t.Optional["AbstractNoteHandler"] = None
		self.hud: t.Optional["HUD"] = None

	@classmethod
	def get_kernel(
		cls,
		game: "Game",
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
		return InGameSceneKernel(cls, game, level_data, difficulty, follow_scene, remaining_week)

	def init_basic_fnf_stuff(self) -> None:
		"""
		Initializes the ``InGameScene``'s standard FNF components.

		This method will:
		  - create a player, girlfriend and opponent character.
		  - create a note handler
		  - create a HUD
		  - load the scene's song and supply the note handler with it.

		This method returns without doing anything if ``self.boyfriend``
		is not ``None``. This may be helpful if custom code in an overridden
		``__init__`` method relies on some of the characters, so it may be
		called from an overridden ``__init__`` method.

		Otherwise, it is called from the ``InGameSceneKernel``'s
		``create_scene`` implementation.
		"""
		if self.boyfriend is not None:
			return

		lev = self.level_data
		bf_p, gf_p, op_p = self.get_character_scene_parameters()

		self.boyfriend = self.create_character(lev.player_character, self.player_anchor, *bf_p)

		if (gf_char_id := lev.girlfriend_character) is None:
			# HACK: Feeding `CharacterData` here is probably a gross violation of something
			self.girlfriend = self.create_object(
				None, None, _ThrowawayGf, self, CharacterData(_ThrowawayGf, "", "")
			)
		else:
			self.girlfriend = self.create_character(gf_char_id, self.girlfriend_anchor, *gf_p)

		self.opponent = self.create_character(lev.opponent_character, self.opponent_anchor, *op_p)

		self.dancers[self.opponent] = DancerInfo(2, 0)
		self.dancers[self.boyfriend] = DancerInfo(2, 0)
		self.dancers[self.girlfriend] = DancerInfo(1, 0)

		if self.focus_targets:
			logger.trace("expect nonstandard focus targets")
		self.focus_targets.append(FocusTargetInfo(self.opponent))
		self.focus_targets.append(FocusTargetInfo(self.boyfriend))

		self.hud = self.create_hud()
		self.hud.update_score(self.score)
		self.hud.update_health(self.health)

		self.note_handler = self.create_note_handler()

		inst, voices, song_data = fetch_song(self.level_data.song_name, self.difficulty)

		self.pause_players()
		self.inst_player.set(inst, play=False)
		if voices is not None:
			self.voice_player.set(voices, play=False)

		self.conductor.bpm = song_data["bpm"]
		self.conductor.load_bpm_changes(song_data)
		self.note_handler.set_song_data(song_data)

		self.song_data = song_data

	def create_note_handler(self) -> "AbstractNoteHandler":
		raise NotImplementedError("Subclass this!")

	def create_hud(self) -> "HUD":
		raise NotImplementedError("Subclass this!")

	def get_character_scene_parameters(self) -> t.Tuple[
		t.Tuple[t.Optional["SceneLayer"], t.Optional[t.Union[t.Iterable["Camera"], "Camera"]]],
		t.Tuple[t.Optional["SceneLayer"], t.Optional[t.Union[t.Iterable["Camera"], "Camera"]]],
		t.Tuple[t.Optional["SceneLayer"], t.Optional[t.Union[t.Iterable["Camera"], "Camera"]]],
	]:
		return ((None, None), (None, None), (None, None))

	def create_character(
		self,
		char_id: t.Hashable,
		anchor: Anchor,
		layer: t.Optional["SceneLayer"],
		cameras: t.Optional[t.Union[t.Iterable["Camera"], "Camera"]],
	) -> Character:
		k = self.game.character_registry[char_id]

		if k.supports_direct_creation():
			char = k.create_direct(self, layer, cameras)
		else:
			logger.warning("This is a not-thought-out code path. Good luck!")
			char = k.create(self)

		char.position = (
			anchor.position.x + char.width * anchor.alignment.x,
			anchor.position.y + char.height * anchor.alignment.y,
		)

		return char

	def ready(self) -> None:
		"""
		Called after `setup` and `load_song` have been called.
		Starts the level by setting the main camera's zoom as well as
		view targets and then calls ``start_countdown``.
		"""
		# NOTE: Typically, characters play an animation when you create them, which then goes on
		# to subtly influence camera focussing.
		# (Or maybe not so subtly, depends on the spritesheet.)
		self.main_cam.zoom = self._default_cam_zoom
		self.main_cam.look_at(
			self.opponent.get_current_frame_dimensions() * 0.5 + Vec2(100.0, 100.0)
		)

		if self.song_data["notes"]:
			self._set_focused_character(int(self.song_data["notes"][0]["mustHitSection"]))

		self.start_countdown()

	def start_countdown(self) -> None:
		"""
		Starts the countdown. Sets the scene's state to
		``GameState.COUNTDOWN``, the song position to 5 beats from zero,
		syncs the conductor from dt/elapsed and schedules
		``self.countdown`` to be called each beat.
		"""
		self._countdown_stage = 0
		self.state = GameState.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		self.sync_conductor_from_dt()
		self.clock.schedule_interval(self.countdown, self.conductor.beat_duration * 0.001)

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
		if not self.do_focus:
			return

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
			self.main_cam.zoom = lerp(self._default_cam_zoom, self.main_cam.zoom, 0.5**(dt*5.0))
			self.hud_cam.zoom = lerp(1.0, self.hud_cam.zoom, 0.5**(dt*5.0))

	def process_input(self, dt: float) -> None:
		"""
		Called with `update` every time.
		Keyboard input should be handled here.
		"""
		key_handler = self.game.key_handler

		# Unheld note types aren't in the dict, held ones are mapped to False,
		# just pressed ones are mapped to True
		held = {
			type_: key_handler.just_pressed(control)
			for type_, control in self.note_handler.NOTE_TO_CONTROL_MAP.items()
			if key_handler[control]
		}
		opponent_hit, player_missed, player_res = self.note_handler.update(held)

		if opponent_hit:
			self.opponent.on_notes_hit(opponent_hit)
			self.zoom_cams = True

		if player_missed:
			self.boyfriend.on_notes_missed(player_missed)
			for note in player_missed:
				self.on_note_miss(note)

		for type_ in NoteType:
			if type_ not in player_res:
				# Note not being held, make the arrow static
				self.hud.arrow_static(type_)
			elif player_res[type_] is None:
				# Note was pressed but player missed
				self.hud.arrow_pressed(type_)
				if held[type_]: # Just pressed
					self.on_misinput(type_)
			else:
				# Note was pressed and player hit
				n = player_res[type_]
				self.hud.arrow_confirm(type_)
				self.boyfriend.on_notes_hit((n,))
				self.on_note_hit(n)

		self.boyfriend.dont_idle = bool(held)

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
		By default, notifies the HUD, causing a combo popup,
		increments score and grants health.
		"""
		self.score += 100
		self.hud.update_score(self.score)

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
		self.boyfriend.on_misinput(type_)
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
					self.game, next_level_data, self.difficulty, self.follow_scene, week_rest
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
			kern = self.game.character_registry[self.boyfriend.character_data.game_over_fallback]
			game_over_bf = kern.create(self)
		else:
			# Definitely do not want to add him to two scenes
			game_over_bf = self.boyfriend
			self.remove(game_over_bf, keep=True)

		game_over_bf.position = tuple(self.boyfriend.get_screen_position(self.main_cam))

		# Do not transition out anymore once the gameover scene has been opened cause the
		# glimpse of a bf-less dead stage is weird
		self.skip_transition_out = True

		self.game.push_scene(scenes.GameOverScene.get_kernel(self.game, game_over_bf))

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
						self.game,
						self.level_data,
						self.difficulty,
						self.follow_scene,
						self.remaining_week,
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
