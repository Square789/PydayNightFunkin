
from platform import python_version
import sys
from time import perf_counter
import typing as t

from loguru import logger
import pyglet

logger.remove(0)
# You really want to leave this set to `True` unless you haven't
# touched the rendering backend AND not seen an OpenGL error for at
# least 20 hours on at least three different systems.
pyglet.options["debug_gl"] = True

from pyday_night_funkin.core import ogg_decoder
from pyday_night_funkin.core.asset_system import load_font
from pyday_night_funkin.core.key_handler import KeyHandler, RawKeyHandler
from pyday_night_funkin.core.pnf_player import PNFPlayer, SFXRing
from pyday_night_funkin.core.pnf_window import PNFWindow
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.constants import GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.save_data import SaveData
from pyday_night_funkin.scenes import TestScene, TitleScene, TriangleScene

if t.TYPE_CHECKING:
	from loguru import Record
	from pyday_night_funkin.core.types import Numeric


__version__ = "0.0.37"


class _FPSData:
	def __init__(self) -> None:
		self.last_second_timestamp = perf_counter() * 1000
		self._reset_measurements()
		self.fmt_fps = "?"
		self.fmt_avg_frame_time = \
		self.fmt_max_frame_time = \
		self.fmt_avg_draw_time = \
		self.fmt_avg_update_time = \
		self.fmt_max_draw_time = \
		self.fmt_max_update_time = float("nan")

	def _reset_measurements(self) -> None:
		self.last_seconds_frames = 0
		self.last_seconds_frame_time = 0
		self.last_seconds_spent_draw_time = 0.0
		self.last_seconds_max_draw_time = -1
		self.last_seconds_spent_update_time = 0.0
		self.last_seconds_max_update_time = -1

	def bump(self, draw_time: "Numeric", update_time: "Numeric") -> None:
		frame_time = draw_time + update_time
		self.last_seconds_frames += 1
		self.last_seconds_frame_time += frame_time
		self.last_seconds_spent_draw_time += draw_time
		self.last_seconds_spent_update_time += update_time
		self.last_seconds_max_draw_time = max(self.last_seconds_max_draw_time, draw_time)
		self.last_seconds_max_update_time = max(self.last_seconds_max_update_time, update_time)

		t = perf_counter() * 1000
		if t - self.last_second_timestamp < 1000:
			return

		self.last_second_timestamp = t
		self.fmt_fps = self.last_seconds_frames
		self.fmt_avg_draw_time = (
			self.last_seconds_spent_draw_time / self.last_seconds_frames
			if self.last_seconds_frames != 0 else float("nan")
		)
		self.fmt_avg_update_time = (
			self.last_seconds_spent_update_time / self.last_seconds_frames
			if self.last_seconds_frames != 0 else float("nan")
		)
		self.fmt_max_draw_time = (
			self.last_seconds_max_draw_time if self.last_seconds_max_draw_time >= 0
			else "?"
		)
		self.fmt_max_update_time = (
			self.last_seconds_max_update_time if self.last_seconds_max_update_time >= 0
			else "?"
		)
		tmp = self.last_seconds_max_update_time + self.last_seconds_max_draw_time
		self.fmt_max_frame_time = tmp if tmp >= 0 else "?"
		self.fmt_avg_frame_time = (self.fmt_avg_update_time + self.fmt_avg_draw_time) / 2
		self._reset_measurements()


class Game:
	def __init__(self) -> None:
		self.debug = True
		self.use_debug_pane = self.debug and False
		# These have to be setup later, see `run`
		self.debug_pane: t.Optional[DebugPane] = None
		self._last_update_time = 0
		self._fps: t.Optional[_FPSData] = None
		self._dt_limit = .35

		self.save_data = SaveData.load()

		self.window = PNFWindow(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = True,
			vsync = False,
			caption = f"PydayNightFunkin' v{__version__}",
		)

		# OpenGL context is probably good here,
		# initialize and set up a bunch of global stuff.
		try:
			from pyday_night_funkin.core.graphics.cygl import gl as cygl
		except ImportError:
			pass
		else:
			from pyglet.gl import gl
			cygl.initialize(gl)

		if ogg_decoder not in pyglet.media.codecs.get_decoders():
			pyglet.media.codecs.add_decoders(ogg_decoder)

		from pyday_night_funkin import base_game_pack
		base_game_pack.load()
		# Load VCR OSD Mono here, before any labels are drawn and stuff.
		# Don't do it in the base game, cause it feels more important than that.
		load_font("fonts/vcr.ttf")

		self.raw_key_handler = RawKeyHandler()
		self.key_handler = KeyHandler(self.save_data.config.key_bindings)

		self.player = PNFPlayer()
		self.sfx_ring = SFXRing()

		self.window.push_handlers(self.key_handler)
		self.window.push_handlers(self.raw_key_handler)
		self.window.push_handlers(on_draw = self.draw)

		self._scene_stack: t.List[BaseScene] = []
		self._scenes_to_draw: t.List[BaseScene] = []
		self._scenes_to_update: t.List[BaseScene] = []
		self._pending_scene_stack_removals = set()
		self._pending_scene_stack_additions = []

		# Push initial scene
		self.push_scene(TitleScene)
		#self.push_scene(TestScene)
		#self.push_scene(TriangleScene)

	def _on_scene_stack_change(self) -> None:
		i = len(self._scene_stack) - 1
		while i > 0 and self._scene_stack[i].draw_passthrough:
			i -= 1
		self._scenes_to_draw = self._scene_stack[i:]

		i = len(self._scene_stack) - 1
		while i > 0 and self._scene_stack[i].update_passthrough:
			i -= 1
		self._scenes_to_update = self._scene_stack[i:]

	def run(self) -> None:
		"""
		Run the game.
		"""
		# Must be set up in the game loop since otherwise some OpenGL
		# stuff will go wrong.
		def setup(_):
			if not self.debug:
				return

			self._fps = _FPSData()

			_stderr_fmt = (
				"<green>{time:MMM DD HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | "
				"<cyan>{name}</cyan>:<cyan>{function}</cyan>@<cyan>{line}</cyan> - "
				"<level>{message}</level>"
			)
			if sys.stderr:
				logger.add(sys.stderr, format=_stderr_fmt)

			def _debug_pane_record_formatter(rec: "Record") -> str:
				elapsed = rec["elapsed"]
				# If you leave this running for more than a day, you're insane. Still:
				days = elapsed.days % 11 # some sanity
				secs = elapsed.seconds + days * 86400
				# secs should not exceed a b10 rep of more than 6 places now
				millisecs = elapsed.microseconds // 1000
				return (
					f"{secs:0>6}.{millisecs:0>3} | {rec['level']:<8} | "
					f"{rec['name']}:{rec['function']}@{rec['line']} - {rec['message']}"
				)

			if self.use_debug_pane:
				self.debug_pane = DebugPane(8)
				logger.add(self.debug_pane.add_message, format=_debug_pane_record_formatter)

			logger.info(
				f"Game started (v{__version__}), pyglet v{pyglet.version}, "
				f"Python v{python_version()}"
			)

		pyglet.clock.schedule_once(setup, 0.0)
		pyglet.clock.schedule_interval(self.update, 1 / 60.0)
		pyglet.app.run()

	def push_scene(self, new_scene_cls: t.Type[BaseScene], *args, **kwargs) -> None:
		"""
		Requests push of a new scene onto the scene stack which will
		then be the topmost scene.
		The game instance will be passed as the first argument to the
		scene class, with any args and kwargs following it.
		Note that this method will not do its job if a scene has
		already been pushed before in this update tick. Use
		`push_scene_always` for that.
		"""
		if not self._pending_scene_stack_additions:
			self._pending_scene_stack_additions.append((new_scene_cls, args, kwargs))

	def push_scene_always(self, new_scene_cls: t.Type[BaseScene], *args, **kwargs) -> None:
		"""
		Requests push of a new scene onto the scene stack, which will
		then be the topmost scene.
		The game instance will be passed as the first argument to the
		scene class, with any args and kwargs following it.
		"""
		self._pending_scene_stack_additions.append((new_scene_cls, args, kwargs))

	def remove_scene(self, scene: BaseScene) -> None:
		"""
		Requests removal of the given scene from anywhere in the
		scene stack.
		"""
		self._pending_scene_stack_removals.add(scene)

	def set_scene(self, new_scene_type: t.Type[BaseScene], *args, **kwargs):
		"""
		Arranges for clearing of the existing scene stack and addition
		of the given scene passed in the same manner as in `push_scene`
		to be its only member. Clears any possibly pending scene
		additions beforehand as well.
		"""
		for scene in self._scene_stack:
			self._pending_scene_stack_removals.add(scene)
		self._pending_scene_stack_additions.clear()

		self.push_scene(new_scene_type, *args, **kwargs)

	def get_previous_scene(self, scene: BaseScene) -> t.Optional[BaseScene]:
		i = self._scene_stack.index(scene)
		return self._scene_stack[i - 1] if i > 0 else None

	def get_next_scene(self, scene: BaseScene) -> t.Optional[BaseScene]:
		i = self._scene_stack.index(scene)
		return self._scene_stack[i + 1] if i < len(self._scene_stack) - 1 else None

	def draw(self) -> None:
		stime = perf_counter()
		self.window.clear()

		for scene in self._scenes_to_draw:
			scene.draw()

		draw_time = (perf_counter() - stime) * 1000
		if self.use_debug_pane:
			self.debug_pane.draw()
			self._fps.bump(draw_time, self._last_update_time)
			# Prints frame x-1's draw time in frame x, but who cares
			self.debug_pane.update(
				self._fps.fmt_fps,
				self._fps.fmt_avg_frame_time,
				self._fps.fmt_max_frame_time,
				self._fps.fmt_avg_update_time,
				self._fps.fmt_max_update_time,
				self._fps.fmt_avg_draw_time,
				self._fps.fmt_max_draw_time,
				draw_time,
				self._last_update_time,
			)
		elif self.debug:
			self._fps.bump(draw_time, self._last_update_time)

	def _modify_scene_stack(self) -> float:
		"""
		Method to apply outstanding modifications to the scene stack.
		This stuff can't be done exactly when a scene demands it since
		then we would be looking at a mess of half-dead scenes still
		running their update code and erroring out. Scary!
		"""
		if self._pending_scene_stack_removals:
			for scene in self._scene_stack[::-1]:
				if scene not in self._pending_scene_stack_removals:
					continue
				self._scene_stack.remove(scene)
				scene.destroy()
			self._on_scene_stack_change()
			self._pending_scene_stack_removals.clear()

		if self._pending_scene_stack_additions:
			while self._pending_scene_stack_additions:
				scene_type, args, kwargs = self._pending_scene_stack_additions.pop()
				new_scene = scene_type(self, *args, **kwargs)
				self._scene_stack.append(new_scene)
			self._on_scene_stack_change()

	def update(self, dt: float) -> None:
		stime = perf_counter()

		if dt > self._dt_limit:
			logger.warning(f"dt exceeding limit ({dt:.4f} > {self._dt_limit:.4f}), capping.")
			dt = self._dt_limit

		for scene in self._scenes_to_update:
			scene.update(dt)

		if self._pending_scene_stack_removals or self._pending_scene_stack_additions:
			self._modify_scene_stack()

		self.key_handler.post_update()
		self.raw_key_handler.post_update()
		self._last_update_time = (perf_counter() - stime) * 1000
