
import typing as t

from loguru import logger
from pyglet.clock import Clock
from pyglet.gl import gl
from pyglet.window.key import B, R

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.scene_context import CamSceneContext, SceneContext
from pyday_night_funkin.core.scene_container import Container, SceneLayer
from pyday_night_funkin.core.tween_effects import EffectController
from pyday_night_funkin.core.utils import to_rgba_tuple

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.asset_system import LoadingRequest
	from pyday_night_funkin.main_game import Game

BaseSceneT = t.TypeVar("BaseSceneT", bound="BaseScene")
SceneKernelT = t.TypeVar("SceneKernelT", bound="SceneKernel")


# NOTE: Wait for le python 3.12 typing: https://peps.python.org/pep-0692/
# or maybe just https://peps.python.org/pep-0646/, works as well.
# This will make it possible to actually have kwargs typed.
# For now, support both a dict and kwargs, so at least something is typed.
class BaseSceneArgDict(t.TypedDict, total=False):
	transition: t.Optional[t.Union[
		t.Type["TransitionScene"],
		t.Tuple[t.Optional[t.Type["TransitionScene"]], t.Optional[t.Type["TransitionScene"]]],
	]]
# NOTE: The stuff facing users the most is `fill`; apart from that `get_kernel` methods
# on scenes, which are special in themselves again cause they may have non-kernel args.
# So by all means preserve the type-hints on `fill`!
# Unfortunately, this currently makes `None` with explicit kwargs ambiguous; requiring the
# use of (None, None) instead on `transition` to achieve the same thing; so i won't be using
# those.

# PARALLEL INHERITANCE HIERARCHY BABYYYYYYYYYYY

class SceneKernel:
	"""
	A `SceneKernel` is fancy-talk for an object storing a scene's
	setup arguments so they may create it at a later time.
	They additionally pass themselves through the `__init__` method of
	a scene and all its superclasses, where any and all scene
	initialization arguments can be written in, overridable by newer
	subclasses.
	"""

	def __init__(self, scene_type: t.Type["BaseScene"], game: "Game", *args, **kwargs) -> None:
		self._scene_type = scene_type
		self._scene_args = args
		self._scene_kwargs = kwargs

		self._uninitialized_kernel_params: t.Set[str] = set()
		self._kernel_params: t.Set[str] = set()

		self.game: "Game" = game

		self.transition: t.Optional[t.Union[
			t.Type["TransitionScene"],
			t.Tuple[t.Optional[t.Type["TransitionScene"]], t.Optional[t.Type["TransitionScene"]]],
		]] = None
		self.register_kernel_params("transition")

	def register_kernel_params(self, *names: str) -> None:
		self._uninitialized_kernel_params.update(names)
		self._kernel_params.update(names)

	def fill(
		self: SceneKernelT,
		arg_dict: t.Optional[BaseSceneArgDict] = None,
		**kwargs
	) -> SceneKernelT:
		"""
		Fills in scene-specific defaults for this kernel to be used by
		scenes during their initialization. If you get the idea that
		this is a clumsy reinvention of kwargs, you'd be correct.

		`"transition"`: A 2-length tuple of: Either a transition scene
		type that will be used for the scene's transition in ([0]) or
		out ([1]), or `None`, in which case no transition happens.
		A single non-tuple argument is equivalent to a 2-length tuple
		with the argument in both positions.
		By default, the standard `TransitionScene` with a simple black 
		adein/out is used for both.
		"""
		arg_dict: BaseSceneArgDict = kwargs if arg_dict is None else arg_dict
		for parameter in self._kernel_params:
			if parameter in arg_dict:
				v = arg_dict.pop(parameter)
				if parameter in self._uninitialized_kernel_params:
					self._uninitialized_kernel_params.remove(parameter)
					setattr(self, parameter, v)

		if arg_dict:
			logger.warning(
				f"Extraneous entry(ies) in argument dict! First one: "
				f"{next(iter(arg_dict))}"
			)

		return self

	def finalize(self) -> None:
		if self._uninitialized_kernel_params:
			logger.warning(
				f"Uninitialized scene kernel parameter(s)! First one: "
				f"{next(iter(self._uninitialized_kernel_params))}"
			)

	def get_loading_hints(self, game: "Game") -> "LoadingRequest":
		"""
		Returns a ``LoadingRequest``, describing assets that, when loaded
		into the asset system cache will have the scene start without stalling
		the main thread for too long.
		"""
		raise NotImplementedError()

	def create_scene(self) -> "BaseScene":
		return self._scene_type(self, *self._scene_args, **self._scene_kwargs)


class BaseScene(Container):
	"""
	A scene holds a number of scene objects and cameras, a batch and
	is the general setting of a chunk of game logic.

	Scenes inherit from ``Container``, allowing for their usage of layers.
	"""

	def __init__(self, kernel: SceneKernel) -> None:
		"""
		Initializes the base scene.

		:param kernel: The `SceneKernel` the scene is initialized from.
		"""
		super().__init__(None, True)

		# NOTE: Scenes are very special and do not have a context at their root,
		# instead overriding ``get_context`` to access ``self.batch`` directly and
		# to produce groups with no parent.
		# This saves on one single group that would otherwise appear in the draw tree.
		self._context = None

		kernel.fill(transition=TransitionScene)
		kernel.finalize()

		self.game = kernel.game

		self.batch = PNFBatch()

		self.draw_passthrough: bool = True
		"""
		Whether scenes in the scene stack after this scene will be
		drawn. `True` by default.
		TODO: Changing does not cause scene stack to be recomputed
		"""

		self.update_passthrough: bool = False
		"""
		Whether scenes in the scene stack after this scene will be
		updated. `False` by default.
		TODO: Changing does not cause scene stack to be recomputed
		"""

		self._next_layer_order = 1

		self._layers: t.List[SceneLayer] = []
		"""
		This scene's layers. Should usually not be interacted with
		directly.
		"""

		self._cameras: t.List[Camera] = []

		self._default_camera: t.Optional[Camera] = None
		"""
		The scene's default camera which will be used if an operation
		needs one but none was given.

		Cameras are potentially expensive objects. The default one will
		be created once an object is created with no other camera given
		or, once ``create_camera`` is called for the first time, will be
		set to the result of that call.
		"""

		if isinstance(kernel.transition, tuple):
			self._transition_in_cls, self._transition_out_cls = kernel.transition
		else:
			self._transition_in_cls = self._transition_out_cls = kernel.transition

		self._transition_out_started: bool = False
		self._transition_out_complete: bool = False
		self._transition_out_next_scene: t.Optional[SceneKernel] = None
		self.skip_transition_out: bool = False
		"""
		A simple attribute that will cause the scene's default
		``on_imminent_replacement`` implementation to just skip the out
		transition and immediatedly call `set_scene` with the passed
		scene kernel.
		"""

		self._passed_time = 0.0
		self.clock = Clock(self._get_elapsed_time)

		self.sfx_ring = self.game.sound.create_sfx_ring()
		"""
		A SFXRing for this scene; destroyed along with it.
		"""

		self.effects = EffectController()
		"""
		The scene's effect controller. Use this for tweening and
		toggling just about anything.
		"""

	@classmethod
	def get_kernel(cls, game: "Game") -> SceneKernel:
		"""
		Creates a `SceneKernel` for this scene, which is necessary to
		delay its creation. See the SceneKernel's class docstring for
		more info.
		"""
		return SceneKernel(cls, game)

	def _get_elapsed_time(self) -> float:
		return self._passed_time

	@t.final
	def set_context(self, _: SceneContext) -> None:
		raise RuntimeError("Can't set a scene's context, it's the scene hierarchy root!")

	@t.final
	def invalidate_context(self) -> None:
		raise RuntimeError("Can't invalidate a scene's context; try `remove_scene` instead!")

	def sort(self, compfn: t.Optional[t.Callable] = None) -> None:
		# HACK: copypaste of superclass's sort
		if self._layers:
			logger.warning(
				"Ordering a container with layers will ruin layer-dictated order."
			)

		self._members.sort(key=compfn)
		for i, m in enumerate(self._members):
			m.set_context_group(PNFGroup(order=i))

	def create_camera(self, w: int = -1, h: int = -1, x: int = 0, y: int = 0) -> Camera:
		if w < 0:
			w = self.game.dimensions[0]
		if h < 0:
			h = self.game.dimensions[1]

		c = Camera(x, y, w, h)
		self._cameras.append(c)
		# HACK: Draw call will fail when nothing is added to a camera otherwise.
		self.batch._get_draw_list(c)

		if self._default_camera is None:
			self._default_camera = c

		return c

	def update(self, dt: float) -> None:
		if self.game.debug:
			if self.game.raw_key_handler.just_pressed(R):
				logger.debug("hello")

			if self.game.raw_key_handler.just_pressed(B):
				print(self.batch.dump_debug_info())

		self._passed_time += dt
		self.clock.tick()

		self.effects.update(dt)

		for c in self._cameras:
			c.update(dt)

		for x in self._members.copy():
			x.update(dt)

	def draw(self) -> None:
		"""
		Draws the scene.
		There should be no reason to override this.
		"""

		# Framebuffer shenanigans stolen from
		# https://learnopengl.com/Advanced-OpenGL/Framebuffers

		# Rendering scheme stolen here.
		# I would like to send Tamschi eternal gratitude.
		# https://stackoverflow.com/questions/2171085/
		# opengl-blending-with-previous-contents-of-framebuffer

		for camera in self._cameras:
			camera.framebuffer.bind()
			# While the viewport is nice to shrink the game, it also affects all draw
			# operations on the cameras, which crams the sprites into their fb's corners.
			# Need to set it to this for framebuffer rendering
			# TODO: Camera system does not work for cameras that are not the same dimensions
			# as the game. Fix that at some point, probably.
			# I have no idea what I am thinking with the math below and what is right and what
			# I want out of life.

			self.game.window.set_viewport((
				# -camera._screen_x,
				# -camera._screen_y,

				0,
				min(0, int(camera._height) - CNST.GAME_HEIGHT),  # weird lower-left translation,
				                                                 # please leave me alone

				# === #

				# CNST.GAME_WIDTH**2 // camera._width,
				# CNST.GAME_HEIGHT**2 // camera._height,

				# camera._width**2 // CNST.GAME_WIDTH,
				# camera._height**2 // CNST.GAME_HEIGHT,

				CNST.GAME_WIDTH,
				CNST.GAME_HEIGHT,

				# camera._width,
				# camera._height,
			))
			gl.glClearColor(*camera.clear_color)
			gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
			gl.glBlendFuncSeparate(
				gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA
			)
			self.batch.draw(camera) # Draw everything in the camera's draw list to the camera's FBO
			camera.framebuffer.unbind() # Binds default fbo again

			self.game.window.set_viewport()
			camera.draw_framebuffer()

		gl.glUseProgram(0)

	def _get_context_group(self) -> PNFGroup:
		return PNFGroup(None, self._get_order())

	def get_context(
		self,
		layer: t.Optional[SceneLayer] = None,
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]] = None,
	) -> CamSceneContext:
		"""
		Creates a ``CamSceneContext`` for a ``SceneObject`` to use.

		The given ``layer`` and ``cameras`` are turned into an appropiate
		``CamSceneContext`` that can be passed onto a child of this scene.

		If no layer is supplied, will add the object under this scene's
		draw tree root directly.

		If no cameras are supplied, will use the first camera created in
		this scene via ``create_cameras``, or create it if none exists.
		"""
		if cameras is None:
			if self._default_camera is None:
				self.create_camera()
			actual_cameras = (self._default_camera,)
		elif isinstance(cameras, Camera):
			actual_cameras = (cameras,)
		else:
			actual_cameras = cameras

		if layer is None:
			return CamSceneContext(self.batch, self._get_context_group(), actual_cameras)
		else:
			# NOTE kinda gross copypaste from Container.get_context
			return layer.get_context(None, actual_cameras)

	def remove_scene(self, *args, **kwargs) -> None:
		"""
		Removes this scene by telling the below scene, or the game if
		this scene is the parent scene, to remove it.
		All args and kwargs will be passed through to a parent scene's
		`on_subscene_removal` method, (with this scene passed before
		as the first arg) but ignored if the game receives the removal
		request.
		"""
		remover = self.game.get_previous_scene(self)
		if remover is None:
			self.game.remove_scene(self)
		else:
			remover.on_subscene_removal(self, *args, **kwargs)

	def on_subscene_removal(self, subscene: "BaseScene", *args, **kwargs) -> None:
		"""
		Called as soon as a direct subscene of this scene is removed
		through `remove_scene`.
		Offers a possibility for scenes to react to subscene removal
		via overriding.
		The default implementation does nothing but actually remove the
		subscene via `self.game.remove_scene`.
		"""
		self.game.remove_scene(subscene)

	def on_imminent_replacement(self, new_scene_kernel: SceneKernel) -> bool:
		"""
		Called on the top scene as soon as the game receives a request
		to replace it via `set_scene`.
		This function receives the new scene's kernel and has the
		ability to deny the switch by returning `False`, which is
		useful for delaying and transitioning out of a scene.
		By default, will start a basic out transition that calls into
		`on_out_transition_complete` upon finishing.
		"""
		if self.skip_transition_out or self._transition_out_complete:
			return True

		if not self._transition_out_started:
			self.start_transition_out(new_scene_kernel)
		else:
			logger.info("Out transition started already, ignoring incoming replacement")

		return False

	def start_transition_in(self) -> None:
		"""
		Starts the "in" transition for a scene. By default, will push
		a basic transition scene with a fade-in that calls
		`on_transition_in_complete` upon finishing.
		This is called by the scene manager after it establishes that a
		scene has been freshly created as the first element of a scene
		stack.
		"""
		if self._transition_in_cls is not None:
			self.game.push_scene(
				self._transition_in_cls.get_kernel(self.game, True, self.on_transition_in_complete)
			)

	def start_transition_out(self, new_scene_kernel: SceneKernel) -> None:
		"""
		Starts the "out" transition for a scene.
		"""
		if self._transition_out_cls is None:
			return

		self.game.push_scene(
			self._transition_out_cls.get_kernel(self.game, False, self.on_transition_out_complete)
		)
		self._transition_out_next_scene = new_scene_kernel
		self._transition_out_started = True

	def on_transition_in_complete(self, transition: "TransitionScene") -> None:
		self.game.remove_scene(transition)

	def on_transition_out_complete(self, transition: "TransitionScene") -> None:
		self._transition_out_complete = True
		if self._transition_out_next_scene is None:
			self.remove_scene()
		else:
			# Should call into `on_imminent_replacement`. If it doesn't, huh, funny.
			# Should probably work out though lol
			self.game.set_scene(self._transition_out_next_scene)

	@t.final
	def delete(self) -> None:
		raise RuntimeError("To delete scenes, use `destroy`!")

	def destroy(self) -> None:
		"""
		Destroys the scene by deleting its members and graphics batch.
		**!** This does not remove the scene from the game's scene
		stack and will cause errors if used improperly.
		Chances are you want to use `remove_scene` instead.
		"""
		for x in self._members.copy():
			x.delete()
		self._members.clear()

		for lyr in self._layers:
			lyr.delete()
		self._layers.clear()

		for cam in self._cameras:
			cam.delete()

		self.sfx_ring.destroy()
		self.effects.destroy()

		self.batch.delete()
		del self.batch
		del self.game # reference breaking or something


class TransitionScene(BaseScene):
	def __init__(
		self,
		kernel: SceneKernel,
		is_in: bool,
		on_end: t.Callable[["TransitionScene"], t.Any],
	) -> None:
		super().__init__(kernel)

		self.update_passthrough = True

		self._was_drawn = False
		self._callback = None

		self.create_transition_effect(is_in, lambda: self._delay_then_end(on_end))

	@classmethod
	def get_kernel(
		cls,
		game: "Game",
		is_in: bool,
		on_end: t.Optional[t.Callable[["TransitionScene"], t.Any]] = None,
	) -> SceneKernel:
		return SceneKernel(cls, game, is_in, on_end)

	def create_transition_effect(self, is_in: bool, on_end: t.Callable[[], t.Any]) -> None:
		"""
		Default transition implementation. Creates a fullscreen quad
		that simply fades in or out.
		"""
		a, b = (255, 0) if is_in else (0, 255)

		self.obscurer = self.create_object()
		self.obscurer.make_rect(
			to_rgba_tuple((CNST.BLACK & 0xFFFFFF00) | a), *self.game.dimensions
		)

		self.effects.tween(
			self.obscurer,
			{"opacity": b},
			0.2 if self.game.debug else 0.5,
			on_complete = None if on_end is None else (lambda _: on_end()),
		)

	def _delay_then_end(self, callback: t.Callable[["TransitionScene"], t.Any]) -> None:
		"""
		Sets the transition scene into such a state that it will wait
		for an additional draw call until `callback` is finally called.
		This guarantees that, if the call was made as the result of
		a tween's on_complete callback, the tween is actually displayed
		in its final form while a possibly time-intensive action caused
		by the callback takes place.
		"""
		self._was_drawn = False
		self._callback = callback

	def update(self, dt: float) -> None:
		super().update(dt)
		if self._callback is not None and self._was_drawn:
			self._callback(self)

	def draw(self) -> None:
		super().draw()
		self._was_drawn = True

	def start_transition_in(self) -> None:
		logger.warning("Ignored attempt to create transition on a transition scene!")

	def start_transition_out(self, _: SceneKernel) -> None:
		logger.warning("Ignored attempt to create transition on a transition scene!")

	def on_subscene_removal(self, subscene: "BaseScene", *args, **kwargs) -> None:
		logger.info("Transition scene is tunneling on_subscene_removal request")
		prev_scene = self.game.get_previous_scene(self)
		if prev_scene is None:
			logger.warning("Transition scene was first in scene stack?")
			super().on_subscene_removal(subscene, *args, **kwargs)
		else:
			prev_scene.on_subscene_removal(subscene, *args, **kwargs)
