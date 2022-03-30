
from time import perf_counter
import typing as t

from loguru import logger
import pyglet

# You really want to leave this set to `True` unless you haven't
# touched the rendering backend AND not seen an OpenGL error for at
# least 20 hours
pyglet.options["debug_gl"] = True

from pyglet.window.key import KeyStateHandler

from pyday_night_funkin import base_game_pack
from pyday_night_funkin.core import ogg_decoder
from pyday_night_funkin.core.pnf_player import PNFPlayer, SFXRing
from pyday_night_funkin.core.pnf_window import PNFWindow
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.constants import GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.core.key_handler import KeyHandler
from pyday_night_funkin.save_data import SaveData
from pyday_night_funkin.scenes import TestScene, TitleScene, TriangleScene

if ogg_decoder not in pyglet.media.get_decoders():
	pyglet.media.add_decoders(ogg_decoder)

__version__ = "0.0.14-dev-B"


class _FPSData:
	def __init__(self) -> None:
		self.last_second_timestamp = perf_counter() * 1000
		self._reset_measurements()
		self.fmt_fps = "?"
		self.fmt_avg_frame_time = float("nan")
		self.fmt_max_frame_time = float("nan")

	def _reset_measurements(self) -> None:
		self.last_seconds_frames = 0
		self.last_seconds_frame_time = 0
		self.max_frame_time = -1

	def bump(self, frame_time: float) -> None:
		self.last_seconds_frames += 1
		self.last_seconds_frame_time += frame_time
		self.max_frame_time = max(self.max_frame_time, frame_time)
		t = perf_counter() * 1000
		if t - self.last_second_timestamp >= 1000:
			self.last_second_timestamp = t
			self.fmt_fps = self.last_seconds_frames
			self.fmt_avg_frame_time = (
				self.last_seconds_frame_time / self.last_seconds_frames
				if self.last_seconds_frames != 0 else float("nan")
			)
			self.fmt_max_frame_time = self.max_frame_time if self.max_frame_time >= 0 else "?"
			self._reset_measurements()


class Game():
	def __init__(self) -> None:
		self.debug = True
		self.use_debug_pane = True
		# These have to be setup later, see `run`
		self._update_time = 0
		self._fps: t.Optional[_FPSData] = None
		self.debug_pane: t.Optional[DebugPane] = None

		self.save_data = SaveData.load()

		self.window = PNFWindow(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = True,
			vsync = False,
		)
		self.window.set_caption(f"PydayNightFunkin' v{__version__}")

		self.pyglet_ksh = KeyStateHandler()
		self.key_handler = KeyHandler(self.save_data.config.key_bindings)

		self.player = PNFPlayer()
		self.sfx_ring = SFXRing()

		self.window.push_handlers(self.key_handler)
		self.window.push_handlers(self.pyglet_ksh)
		self.window.push_handlers(on_draw = self.draw)

		self._scene_stack: t.List[BaseScene] = []
		self._scenes_to_draw: t.List[BaseScene] = []
		self._scenes_to_update: t.List[BaseScene] = []
		self._pending_scene_stack_removals = set()
		self._pending_scene_stack_additions = []

		# Asset system related setup
		base_game_pack.load()
		from pyday_night_funkin.alphabet import AlphabetCharacter
		AlphabetCharacter.init_animation_dict()

		# Push initial scene
		self.push_scene(TitleScene)
		#self.push_scene(TestScene)
		#self.push_scene(TriangleScene)

	def _on_scene_stack_change(self) -> None:
		for self_attr, scene_attr in (
			("_scenes_to_draw", "draw_passthrough"),
			("_scenes_to_update", "update_passthrough"),
		):
			start = len(self._scene_stack) - 1
			while start >= 0 and getattr(self._scene_stack[start], scene_attr):
				start -= 1
			setattr(self, self_attr, self._scene_stack[start:])

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
			if self.use_debug_pane:
				self.debug_pane = DebugPane(8)
				logger.add(
					self.debug_pane.add_message,
					format = "{time:mm:ss.SSS} | {level:<8} | {name}{function}{line} - {message}",
				)
			logger.info(f"Game started (v{__version__}), pyglet version {pyglet.version}")
		pyglet.clock.schedule_once(setup, 0.0)

		if not self.debug:
			logger.remove(0)

		pyglet.clock.schedule_interval(self.update, 1 / 60.0)
		pyglet.app.run()

	def push_scene(self, new_scene_cls: t.Type[BaseScene], *args, **kwargs) -> None:
		"""
		Requests push of a new scene onto the scene stack which will then
		be the topmost scene.
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
		Clears the existing scene stack and then sets the given scene
		passed in the same manner as in `push_scene` to be its only
		member.
		"""
		for scene in self._scene_stack:
			self._pending_scene_stack_removals.add(scene)

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
			self._fps.bump(draw_time + self._update_time)
			# Prints frame x-1's draw time in frame x, but who cares
			self.debug_pane.update(
				self._fps.fmt_fps,
				self._fps.fmt_avg_frame_time,
				self._fps.fmt_max_frame_time,
				draw_time,
				self._update_time,
			)
		elif self.debug:
			self._fps.bump(draw_time + self._update_time)

	def _modify_scene_stack(self) -> float:
		"""
		Method to apply outstanding modifications to the scene stack.
		This stuff can't be done exactly when a scene demands it since
		then we would be looking at a mess of half-dead scenes still
		running their update code and erroring out. Scary!
		"""
		stk_mod_t = perf_counter()
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

		return perf_counter() - stk_mod_t

	def update(self, dt: float) -> None:
		stime = perf_counter()

		# TODO: This feels really incorrect, but I can't seem to figure out a
		# better way to prevent scene creation time leaking into the scene's first
		# update call.
		if self._pending_scene_stack_removals or self._pending_scene_stack_additions:
			dt -= self._modify_scene_stack()

		for scene in self._scenes_to_update:
			scene.update(dt)

		self._update_time = (perf_counter() - stime) * 1000
