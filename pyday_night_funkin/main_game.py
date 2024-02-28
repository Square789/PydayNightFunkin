
from math import ceil
from platform import python_version
import queue
import sys
from time import perf_counter
import typing as t

from loguru import logger
import pyglet

import pyday_night_funkin.core.asset_system
from pyday_night_funkin.core.key_handler import KeyHandler, RawKeyHandler
from pyday_night_funkin.core import ogg_decoder
from pyday_night_funkin.core.pnf_window import PNFWindow
from pyday_night_funkin.core.scene_manager import SceneManager
from pyday_night_funkin.core.sound import SoundController
from pyday_night_funkin.constants import GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.enums import Control
from pyday_night_funkin.volume_control_dropdown import VolumeControlDropdown
from pyday_night_funkin.save_data import SaveData
from pyday_night_funkin.registry import Registry
from pyday_night_funkin.scenes import FreeplayScene, TestScene, TitleScene, TriangleScene

if t.TYPE_CHECKING:
	from loguru import Record
	from pyday_night_funkin.character import CharacterData
	from pyday_night_funkin.content_pack import ContentPack, WeekData
	from pyday_night_funkin.core.superscene import SuperScene


__version__ = "0.0.52"


SOUND_GRANULARITY = 10


class _FPSData:
	def __init__(self) -> None:
		self._debug_pane = None

		self.last_second_timestamp = perf_counter()

		self._reset_measurements()

		self.fmt_ups = 0
		self.fmt_dps = 0
		self.fmt_last_timeslice_update_avg = "?"
		self.fmt_last_timeslice_update_max = "?"
		self.fmt_last_timeslice_draw_avg = "?"
		self.fmt_last_timeslice_draw_max = "?"

	def disconnect_debug_pane(self) -> None:
		self._debug_pane = None

	def connect_debug_pane(self, debug_pane: DebugPane):
		self._debug_pane = debug_pane

	def _reset_measurements(self) -> None:
		self.cur_timeslice_update_time = 0.0
		self.cur_timeslice_max_update_time = -1.0
		self.cur_timeslice_draw_time = 0.0
		self.cur_timeslice_max_draw_time = -1.0
		self._updates_cur_timeslice = 0
		self._draws_cur_timeslice = 0

	def bump_draw(self, draw_time: float) -> None:
		self.cur_timeslice_draw_time += draw_time
		self.cur_timeslice_max_draw_time = max(self.cur_timeslice_max_draw_time, draw_time)
		self._draws_cur_timeslice += 1
		if self._debug_pane is not None:
			self._debug_pane.bump_draw_graph(draw_time)

	def bump_update(self, update_time: float) -> None:
		self.cur_timeslice_update_time += update_time
		self.cur_timeslice_max_update_time = max(self.cur_timeslice_max_update_time, update_time)
		self._updates_cur_timeslice += 1
		if self._debug_pane is not None:
			self._debug_pane.bump_update_graph(update_time)

		_ts = perf_counter()
		if _ts - self.last_second_timestamp < 1.0:
			return

		# A second has passed, recalculate our averages
		# Do it in update, since sanely it'd be called more often than draw
		self.fmt_ups = self._updates_cur_timeslice
		self.fmt_dps = self._draws_cur_timeslice
		self.last_second_timestamp = _ts

		self.fmt_last_timeslice_draw_avg = (
			f"{self.cur_timeslice_draw_time / self._draws_cur_timeslice:>4.1f}"
			if self._draws_cur_timeslice != 0 else "?"
		)
		self.fmt_last_timeslice_update_avg = (
			f"{self.cur_timeslice_update_time / self._updates_cur_timeslice:>4.1f}"
			if self._updates_cur_timeslice != 0 else "?"
		)
		self.fmt_last_timeslice_draw_max = (
			f"{self.cur_timeslice_max_draw_time:>5.1f}"
			if self.cur_timeslice_max_draw_time >= 0.0 else "?"
		)
		self.fmt_last_timeslice_update_max = (
			f"{self.cur_timeslice_max_update_time:>5.1f}"
			if self.cur_timeslice_max_update_time >= 0.0 else "?"
		)
		self._debug_pane.update_averages(
			self.fmt_ups,
			self.fmt_dps,
			self.fmt_last_timeslice_update_avg,
			self.fmt_last_timeslice_update_max,
			self.fmt_last_timeslice_draw_avg,
			self.fmt_last_timeslice_draw_max,
		)

		self._reset_measurements()


class Game(SceneManager):
	def __init__(self, debug_level: int, vsync: bool) -> None:
		super().__init__()

		self.debug = debug_level > 0
		self.use_debug_pane = debug_level > 1
		self.debug_pane = None
		self._debug_queue = None
		self.dt_limit = 0.1

		self._last_draw_time = 0.0
		self._fps = _FPSData()
		self._superscenes: t.List["SuperScene"] = []

		logger.remove(0)

		if self.debug:
			def elapsed_patcher(record: "Record") -> None:
				elapsed = record["elapsed"]
				# If you leave this running for more than a day, you're insane. Still:
				days = elapsed.days % 11 # some sanity
				secs = elapsed.seconds + days * 86400
				# secs should not exceed a b10 rep of more than 6 places now
				millisecs = elapsed.microseconds // 1000
				record["extra"]["elapsed_secs_total"] = secs
				record["extra"]["elapsed_millisecs_total"] = millisecs

			logger.configure(patcher=elapsed_patcher)

			if sys.stderr:
				_stderr_fmt = (
					"<green>{time:MMM DD HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | "
					"<cyan>{name}</cyan>:<cyan>{function}</cyan>@<cyan>{line}</cyan> - "
					"<level>{message}</level>"
				)
				logger.add(sys.stderr, format=_stderr_fmt)

			if self.use_debug_pane:
				self._debug_queue = queue.Queue()
				# According to the loguru docs, the string format option appends `\n{exception}`,
				# however the exception is massive and does not belong in the debug pane and the
				# newline creates a box character on the debug pane's single-line labels.
				# Thus, this is a lambda parroting the format string.
				_debug_pane_fmt = lambda _: (
					"{extra[elapsed_secs_total]:0>6}.{extra[elapsed_millisecs_total]:0>3} | "
					"{level:<8} | {name}:{function}@{line} - {message}"
				)
				logger.add(self._debug_queue.put, format=_debug_pane_fmt, colorize=False)

		if ogg_decoder not in pyglet.media.codecs.get_decoders():
			pyglet.media.codecs.add_decoders(ogg_decoder)

		self.dimensions = (GAME_WIDTH, GAME_HEIGHT)
		"""
		The intended pixel size of the game and each of its scenes.
		This does not reflect the true window dimensions or the
		dimensions the scenes may be drawn in, but it will be the world
		space seen in a scene with an unzoomed camera.
		"""

		self.window = PNFWindow(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = True,
			vsync = vsync,
			caption = f"PydayNightFunkin' v{__version__}",
			config = pyglet.gl.Config(double_buffer=True, major_version=4, minor_version=5),
		)

		# OpenGL context is probably good here, initialize and set up this global horribleness.
		from pyday_night_funkin.core.graphics.cygl import gl as cygl
		from pyglet.gl import gl
		cygl.initialize(gl)
		logger.info("cygl module initialized.")

		self.assets = pyday_night_funkin.core.asset_system.initialize(pyglet.clock.get_default())
		self._most_recent_cache_stats = self.assets.get_cache_stats()

		self.volume_control = VolumeControlDropdown(SOUND_GRANULARITY)
		self._superscenes.append(self.volume_control)

		if self.use_debug_pane:
			self.debug_pane = DebugPane(8, self._debug_queue, 140, 140)
			self._superscenes.append(self.debug_pane)
			self._fps.connect_debug_pane(self.debug_pane)

		self.save_data = SaveData.load()

		self.raw_key_handler = RawKeyHandler()
		self.key_handler: KeyHandler[Control] = KeyHandler(self.save_data.config.key_bindings)

		self.window.push_handlers(self.key_handler)
		self.window.push_handlers(self.raw_key_handler)
		self.window.push_handlers(on_draw=self.draw, on_close=self.on_close)

		self.sound = SoundController(SOUND_GRANULARITY)
		if self.debug:
			self.sound.change_volume(-SOUND_GRANULARITY // 2)

		self.player = self.sound.create_player()
		"""
		A single global media player, similar to `FlxG.sound.music`.
		"""

		self.character_registry: Registry["CharacterData"] = Registry()
		self.weeks: t.List["WeekData"] = []
		self._registered_packs: t.Dict[t.Hashable, t.List[int]] = {}
		"""
		Maps registered content packs to the indices they span in
		`self.weeks`.
		"""

		# Load VCR OSD Mono before any labels are drawn and stuff.
		# Don't do it in the base game, cause it feels more important than that.
		pyglet.font.add_file("assets/fonts/vcr.ttf")

		from pyday_night_funkin import base_game_pack
		self.add_content_pack(base_game_pack.load(self))
		# NOTE: Can be omitted
		self.assets.discover_libraries()

		# Push initial scene
		self.push_scene(TitleScene)
		#self.push_scene(FreeplayScene)
		#self.push_scene(TestScene)
		#self.push_scene(TriangleScene)

	def on_close(self) -> None:
		pass
		# NOTE: Not yet.
		# try:
		# 	self.save_data.save()
		# except OSError as e:
		# 	logger.exception(f"Failed writing savedata", e)

	# The method below is subject to extremely heavy change
	def add_content_pack(self, pack: "ContentPack") -> None:
		pack_id = pack.pack_id
		if pack_id in self._registered_packs:
			raise ValueError(f"ContentPack with id {pack_id!r} already registered!")

		for char_id, char_data in pack.characters.items():
			self.character_registry.add(pack_id, char_id, char_data)

		new_week_range_start = len(self.weeks)
		self.weeks.extend(pack.weeks)
		self._registered_packs[pack_id] = list(range(new_week_range_start, len(self.weeks)))

	def run(self) -> None:
		"""
		Runs the game.
		"""

		if self.debug:
			pyglet.clock.schedule_once(
				lambda _: logger.info(
					f"Game started (v{__version__}), pyglet v{pyglet.version}, "
					f"Python v{python_version()}"
				),
				0.0,
			)

		pyglet.clock.schedule_interval(self.update, 1 / 60)
		pyglet.clock.schedule_interval(self.window.draw, 1 / 60)
		pyglet.app.run(None)

	def update(self, dt: float) -> None:
		stime = perf_counter()

		if dt > self.dt_limit:
			dt = self.dt_limit

		for scene in self._scenes_to_update:
			scene.update(dt)

		if self._pending_scene_stack_removals or self._pending_scene_stack_additions:
			self._modify_scene_stack()

		vup = self.key_handler.just_pressed(Control.VOLUME_UP)
		vdn = self.key_handler.just_pressed(Control.VOLUME_DOWN)
		if vup != vdn:
			self.sound.change_volume(1 if vup else -1)
			self.volume_control.display_change(self.sound.selected_volume)
		self.volume_control.update(dt)

		self.key_handler.post_update()
		self.raw_key_handler.post_update()

		if self.debug:
			self._fps.bump_update((perf_counter() - stime) * 1000.0)

		# NOTE: This causes a lie; the debug pane update is not taken into account.
		# You can't really be perfect there, but it does suck since i'm pretty sure
		# laying labels out takes significant time. Oh well!
		if self.use_debug_pane:
			self.debug_pane.update()
			s = self.assets.get_cache_stats()
			if s != self._most_recent_cache_stats:
				# No need to update the label that often
				self.debug_pane.memory_label.text = (
					f"Objects in cache: {s.object_count}\n"
					f"Approximate RAM usage: {ceil(s.system_memory_used / 1024):>3_}KiB\n"
					f"Approximate VRAM usage: {ceil(s.gpu_memory_used / 1024):>3_}KiB"
				)
				self._most_recent_cache_stats = s

	def draw(self) -> None:
		stime = perf_counter()

		self.window.clear()

		for scene in self._scenes_to_draw:
			scene.draw()

		for superscene in self._superscenes:
			superscene.draw()

		self._fps.bump_draw((perf_counter() - stime) * 1000.0)
