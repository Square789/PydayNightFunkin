
from enum import IntEnum
import random
import typing as t

from loguru import logger
from pyglet.math import Vec2

from pyday_night_funkin.base_game_pack import SongResourceOptions, load_song
from pyday_night_funkin.character import Character
from pyday_night_funkin.core.pnf_player import PNFPlayer
from pyday_night_funkin.core.utils import lerp
from pyday_night_funkin.enums import ANIMATION_TAG, CONTROL, DIFFICULTY
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.note import NOTE_TYPE, SUSTAIN_STAGE, Note
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.content_pack import LevelData
	from pyday_night_funkin.core.scene import BaseScene
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.note_handler import AbstractNoteHandler


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


class GAME_STATE(IntEnum):
	LOADING = 0
	COUNTDOWN = 1
	PLAYING = 2
	ENDED = 3


class InGameScene(scenes.MusicBeatScene):
	"""
	Main game driver scene.
	Meant to be a jumble of sprites, players, handlers etc. running the
	entire game.
	Note that this base class only provides a small shred of
	functionality, for it to be playable it needs to be expanded
	by subclassing it (see existing weeks for examples).
	"""

	def __init__(
		self,
		game: "Game",
		level_data: "LevelData",
		difficulty: DIFFICULTY,
		follow_scene: t.Type["BaseScene"],
		remaining_week: t.Sequence["LevelData"] = (),
	) -> None:
		"""
		Initializes the InGame scene.

		:param game: The game the scene runs under.
		:param level_data: The level to be loaded. Heavily influences
		how the scene will play out.
		:param difficulty: Difficulty the scene plays in.
		:param follow_scene: Which scene type to push once the scene
		is over and `remaining_week` is exhausted or when the game is
		stopped otherwise by the user.
		:param remaining_week: A sequence of more `LevelData` to be
		turned into scenes that follow if the user wins this level.
		This runs the story mode.
		"""

		super().__init__(game)

		self.level_data = level_data

		if self.game.player.playing:
			self.game.player.pause()

		self.draw_passthrough = False

		self.difficulty = difficulty
		self.follow_scene = follow_scene
		self.remaining_week = remaining_week

		self.state = GAME_STATE.LOADING

		self.inst_player = PNFPlayer()
		self.voice_player = PNFPlayer()
		# Player group kept throwing exceptions on tutorial which doesn't have vocals
		# Although internally it does more than just play and pause sequentially,
		# doing just that instead seems to sound the same and doesn't cause any
		# crashes.
		# self.song_players = PlayerGroup((self.inst_player, self.voice_player))

		self.song_data: t.Optional[t.Dict] = None

		self.health: float = 0.5
		self.combo: int = 0
		self.score: int = 0

		self._last_followed_singer: int = 0
		self.zoom_cams: bool = False

		self.gf_speed: int = 1
		"""
		Causes `self.girlfriend.dance` to be called on each xth beat.
		"""

		self.setup()
		self.load_song()
		self.ready()

	@staticmethod
	def get_default_cam_zoom() -> float:
		"""
		Returns the default camera zoom.
		"""
		return 1.05

	# Override from BaseScene
	@staticmethod
	def get_default_cameras() -> t.Sequence[t.Union[str, t.Tuple[str, int, int]]]:
		return ("main", "hud")

	def create_note_handler(self) -> "AbstractNoteHandler":
		raise NotImplementedError("Subclass this!")

	def create_hud(self) -> "HUD":
		raise NotImplementedError("Subclass this!")

	def create_player(self, char_cls: t.Type["Character"]) -> "Character":
		"""
		This function should create the player character on stage already
		given the character type.
		By default, the sprite is expected to have the following
		animations:
		`[x]_note_[y]` for x in (`sing`, `miss`)
		and y in (`left`, `down`, `right`, `up`), as well as
		`game_over_[x]` for x in (`ini`, `loop`, `confirm`).
		"""
		raise NotImplementedError("Subclass this!")

	def create_girlfriend(self, char_cls: t.Type["Character"]) -> "Character":
		"""
		This function should create gf, or some kind of replacement
		background decoration bopper already given the character
		type.
		This function is not always called, as level data is allowed
		to set this entry to `None`.
		"""
		raise NotImplementedError("Subclass this!")

	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		"""
		This function should create the level's opponent, already given
		the character type.
		The opponent sprite is expected to have the following
		animations:
		`sing_note_[x]` for x in (`left`, `down`, `right`, `up`).
		"""
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

		char_reg = self.game.character_registry
		level_data = self.level_data

		self.boyfriend = self.create_player(char_reg[level_data.player_character])

		if level_data.girlfriend_character is None:
			self.girlfriend = self.create_object(
				"girlfriend", "main", object_class=_ThrowawayGf, scene=self, x=-100, y=-100
			)
		else:
			self.girlfriend = self.create_girlfriend(char_reg[level_data.girlfriend_character])

		self.opponent = self.create_opponent(char_reg[level_data.opponent_character])

		self.main_cam = self.cameras["main"]
		self.hud_cam = self.cameras["hud"]

		self.hud = self.create_hud()
		self.hud.update_score(0)
		self.hud.update_health(0.5)

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
		self.state = GAME_STATE.PLAYING

	def ready(self) -> None:
		"""
		Called after `setup` and `load_song` have been called.
		Should be used to start the level.
		"""
		# NOTE: This is somewhat of a hack. In the original game, characters play
		# an animation when you create them, I don't feel like copying that so
		# they switch to their idle animation's first frame here.
		# Yes, for FlipIdleCharacters, this means differrent behavior from the default
		# game. If you have complaints about that go send them to your nearest recycling bin.
		for c in (self.boyfriend, self.girlfriend, self.opponent):
			c.dance()

		self.main_cam.zoom = self.get_default_cam_zoom()
		self.main_cam.look_at(self.opponent.get_midpoint() + Vec2(400, 0))

		self._countdown_stage = 0
		self.state = GAME_STATE.COUNTDOWN
		self.conductor.song_position = self.conductor.beat_duration * -5
		self.sync_conductor_from_dt()
		self.clock.schedule_interval(
			self.countdown, self.conductor.beat_duration * 0.001
		)

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
		if self.health < 0.0 and self.state is not GAME_STATE.ENDED:
			# Game over may have been triggered in process_input already
			self.on_game_over()

		# Camera following
		if (cur_section := self.get_current_section()) is not None:
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
			self.opponent.animation.play(f"sing_note_{op_note.type.name.lower()}", True)
			self.zoom_cams = True

		if player_missed:
			for note in player_missed:
				self.on_note_miss(note)
			fail_note = player_missed[-1]
			self.boyfriend.animation.play(f"miss_note_{fail_note.type.name.lower()}", True)

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
		self.boyfriend.animation.play(f"sing_note_{note.type.name.lower()}", True)

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
		self.boyfriend.animation.play(f"miss_note_{type_.name.lower()}", True)
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

		if (sec := self.get_current_section()) is not None and sec["mustHitSection"]:
			self.opponent.dance()

		if self.zoom_cams and self.main_cam.zoom < 1.35 and self.cur_beat % 4 == 0:
			self.main_cam.zoom += 0.015
			self.hud_cam.zoom += 0.03

		if self.cur_beat % self.gf_speed == 0:
			self.girlfriend.dance()

		# This code's purpose should be to get bf out of special animations such as
		# the bopeebo v-signs
		t = self.boyfriend.animation.current.tags
		if not (ANIMATION_TAG.MISS in t or ANIMATION_TAG.SING in t):
			self.boyfriend.dance()

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
		self.state = GAME_STATE.ENDED
		if self.remaining_week:
			next_level, *week_rest = self.remaining_week
			self.game.set_scene(
				next_level.stage_class,
				next_level,
				self.difficulty,
				self.follow_scene,
				week_rest,
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
		self.state = GAME_STATE.ENDED
		game_over_bf = self.create_player(type(self.boyfriend))
		scx, scy = self.boyfriend.get_screen_position(self.main_cam)
		game_over_bf.position = (scx, scy)
		# In case bf is created with `create_object`, which will add him to 2
		# scenes at the same time, which you definitely do not want
		self.remove(game_over_bf, keep=True)
		self.game.push_scene(scenes.GameOverScene, game_over_bf)

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

	def on_subscene_removal(self, subscene, end_self, reset=False):
		super().on_subscene_removal(subscene)
		if end_self:
			self.game.set_scene(self.follow_scene)
		else:
			if not reset:
				if self.state is GAME_STATE.PLAYING:
					self.play_players()
					self.resync()
			else:
				self.game.set_scene(
					self.level_data.stage_class,
					self.level_data,
					self.difficulty,
					self.follow_scene,
					self.remaining_week,
				)

	def destroy(self) -> None:
		super().destroy()
		self.voice_player.delete()
		self.inst_player.delete()
