
from collections import OrderedDict
import typing as t

from loguru import logger
from pyglet.clock import Clock
from pyglet.gl import gl
from pyglet.window.key import B, R

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.scene_context import SceneContext
from pyday_night_funkin.core.scene_object import Container, SceneObject
from pyday_night_funkin.core.tween_effects import EffectController
from pyday_night_funkin.core.utils import to_rgba_tuple

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game

SceneObjectT = t.TypeVar("SceneObjectT", bound=SceneObject)
BaseSceneT = t.TypeVar("BaseSceneT", bound="BaseScene")
SceneKernelT = t.TypeVar("SceneKernelT", bound="SceneKernel")


class OrderedLayer:
	"""
	Signals the `BaseScene` constructor to create an ordered layer
	with the given name.
	"""
	__slots__ = ("name",)

	def __init__(self, name: t.Hashable) -> None:
		self.name = name


class _Layer:
	"""
	A layer is the scene's last intermediate step to the group system.
	Its only point really is the `get_group` function; see its doc.
	"""

	__slots__ = ("group", "force_order", "latest_order")

	def __init__(self, group: PNFGroup, force_order: bool) -> None:
		self.group = group
		self.force_order = force_order
		self.latest_order = 0

	def get_group(self) -> PNFGroup:
		"""
		Returns a group to attach an object to on this layer.

		A layer with forced order will create and return an
		incrementally ordered subgroup with the layer's group as its
		parent.
		A layer without forced order will simply return its group.
		"""
		# TODO: Not really relevant in practice, but the order will
		# keep increasing ad infinitum, I don't like that a lot
		if self.force_order:
			new_groups_order = self.latest_order
			self.latest_order += 1
			return PNFGroup(self.group, new_groups_order)
		else:
			return self.group


# NOTE: Wait for le python 3.12 typing: https://peps.python.org/pep-0692/
# or maybe just https://peps.python.org/pep-0646/, works as well.
# This will make it possible to actually have kwargs typed.
# For now, support both a dict and kwargs, so at least something is typed.
class BaseSceneArgDict(t.TypedDict, total=False):
	layers: t.Optional[t.Sequence[t.Union[t.Hashable, OrderedLayer]]]
	cameras: t.Optional[t.Sequence[t.Hashable]]
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
	They additionally pass themselves through the stack of a scene's
	`__init__` methods, where any and all scene initialization
	arguments can be written in, overridable by newer subclasses.
	"""

	def __init__(self, scene_type: t.Type["BaseScene"], *args, **kwargs) -> None:
		self._scene_type = scene_type
		self._scene_args = args
		self._scene_kwargs = kwargs

		self._uninitialized_kernel_params: t.Set[str] = set()
		self._kernel_params: t.Set[str] = set()

		self.game: t.Optional["Game"] = None

		self.layers: t.Optional[t.Sequence[t.Union[t.Hashable, OrderedLayer]]] = None
		self.cameras: t.Optional[t.Sequence[t.Hashable]] = None
		self.transition: t.Optional[t.Union[
			t.Type["TransitionScene"],
			t.Tuple[t.Optional[t.Type["TransitionScene"]], t.Optional[t.Type["TransitionScene"]]],
		]] = None
		self.register_kernel_params("layers", "cameras", "transition")

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
		scenes during their initialization.

		`"layers"`: A sequence of layer names to be used for this
		scene. The layers can later be referenced by name in
		`create_object` and `add`. The layers will be drawn
		first-to-last as they are given.
		By default, the order in which drawables on the same layer
		are drawn is undefined. It's possible to force each
		drawable onto its own layer subgroup by specifying
		`OrderedLayer("my_layer")` instead of just the layer name
		`"my_layer"`, which may prevent drawing optimizations.
		This should be used only when necessary.
		By default, a single unordered layer by the name of `_default`
		is created.

		`"cameras"` A sequence of camera names to be used for this
		scene's cameras. They can later be referenced by that name in
		`create_object` and `add`.
		By default, a single camera by the name of `_default` is
		created.

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

	def finalize(self):
		if self._uninitialized_kernel_params:
			logger.warning(
				f"Uninitialized scene kernel parameter(s)! First one: "
				f"{next(iter(self._uninitialized_kernel_params))}"
			)

	def create_scene(self, game: "Game") -> "BaseScene":
		self.game = game
		return self._scene_type(self, *self._scene_args, **self._scene_kwargs)


class BaseScene(Container):
	"""
	A scene holds a number of scene objects and cameras, a batch and
	is the general setting of a chunk of game logic.
	"""

	def __init__(self, kernel: SceneKernel) -> None:
		"""
		Initializes the base scene.

		:param kernel: The `SceneKernel` the scene is initialized from.
		"""
		super().__init__()

		kernel.fill(
			layers = ("_default",),
			cameras = ("_default",),
			transition = TransitionScene,
		)
		kernel.finalize()

		self.game = kernel.game

		self.batch = PNFBatch()

		self.draw_passthrough: bool = True
		"""
		Whether scenes in the scene stack after this scene will be
		drawn. `True` by default.
		"""

		self.update_passthrough: bool = False
		"""
		Whether scenes in the scene stack after this scene will be
		updated. `False` by default.
		"""

		self.layers: t.Dict[t.Hashable, _Layer] = OrderedDict()
		"""
		This scene's layers. Should usually not be interacted with
		directly.
		"""

		if not kernel.layers:
			raise ValueError("Scenes must at least have one layer!")

		for i, x in enumerate(kernel.layers):
			if isinstance(x, OrderedLayer):
				name = x.name
				ordered = True
			else:
				name = x
				ordered = False
			if name is None:
				raise TypeError("`None` is not a valid layer name!")
			self.layers[name] = _Layer(PNFGroup(order=i), ordered)

		self.default_layer = next(iter(self.layers.values()))
		"""
		The first layer which will be used in case no layer is given to
		methods requiring one.
		This is the layer created from the first value of the scene
		kernel's `layers`.
		"""

		if not kernel.cameras:
			raise ValueError("Scenes must have at least one camera!")

		self.cameras = OrderedDict(
			(name, Camera(0, 0, w, h)) for name, w, h in (
				(x, *self.game.dimensions) if not isinstance(x, tuple) else x
				for x in kernel.cameras
			)
		)
		"""This scene's cameras."""

		self.default_camera = next(iter(self.cameras.values()))
		"""
		The scene's default camera which will be used if an operation
		needs one but none was given.
		This is the camera created from the first value of the scene
		kernel's `cameras`.
		"""

		# NOTE: Draw call will fail when nothing is added to a camera otherwise.
		for cam in self.cameras.values():
			self.batch._get_draw_list(cam)

		kt = kernel.transition
		if isinstance(kt, tuple):
			self._transition_in_cls, self._transition_out_cls = kt
		else:
			self._transition_in_cls = self._transition_out_cls = kt

		self._transition_out_started: bool = False
		self._transition_out_complete: bool = False
		self._transition_out_next_scene: t.Optional[SceneKernel] = None
		self.skip_transition_out: bool = False
		"""
		A simple attribute that will cause the scene's default
		`start_transition_out` implementation to just skip the out
		transition and immediatedly call `set_scene` with the
		passed scene kernel.
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
	def get_kernel(cls) -> SceneKernel:
		"""
		Creates a `SceneKernel` for this scene, which is necessary to
		delay its creation. See the SceneKernel's class docstring for
		more info.
		"""
		return SceneKernel(cls)

	def _get_elapsed_time(self) -> float:
		return self._passed_time

	# object_class is given as a kwarg somewhere.
	# layer and cameras may also appear either as arg or kwarg.
	@t.overload
	def create_object(
		self,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
		*,
		object_class: t.Type[SceneObjectT],
		**kwargs,
	) -> SceneObjectT:
		...

	# Everything is listed positionally, object_class is arg 3
	@t.overload
	def create_object(
		self,
		layer: t.Optional[str],
		cameras: t.Optional[t.Union[str, t.Iterable[str]]],
		object_class: t.Type[SceneObjectT],
		*args,
		**kwargs,
	) -> SceneObjectT:
		...

	# object_class is not given, return type is PNFSprite.
	@t.overload
	def create_object(
		self,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
		**kwargs,
	) -> PNFSprite:
		...

	def create_object(
		self,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
		object_class: t.Type[SceneObjectT] = PNFSprite,
		*args,
		**kwargs,
	) -> t.Union[SceneObjectT, PNFSprite]:
		"""
		Creates a scene object on the given layer belonging to one or
		multiple cameras. If one or more camera names are specified
		(and the cameras exist in the scene), the object will be
		registered with them.
		If no camera name is specified, the object will be attached to
		the scene's default camera.
		The object will be created from the given `object_class` type
		with all args and kwargs. Note that because they are so
		fundamental, by default the object class is `PNFSprite`.
		The object will be given a fitting `context` filled
		in by the scene if not otherwise given. (And if you give it a
		custom one, you better know what you're doing.)

		Note that `self.create_object("lyr", "cam", Cls, 1, 2, n=3)`
		is effectively equivalent to
		`x = Cls(1, 2, n=3); self.add(x, "lyr", "cam")`, but a bit
		faster as no migration from a virtual batch to the scene's
		batch has to happen.
		"""
		if "context" not in kwargs:
			kwargs["context"] = self.get_context(layer, cameras)

		member = object_class(*args, **kwargs)
		self._members.append(member)
		return member

	@t.final
	def set_context(self, _: SceneContext) -> None:
		raise RuntimeError("Can't set a scene's context, it's the scene hierarchy root!")

	@t.final
	def invalidate_context(self) -> None:
		raise RuntimeError("Can't invalidate a scene's context; try `remove_scene` instead!")

	def add(
		self,
		obj: SceneObject,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
	) -> None:
		"""
		Adds a SceneObject to the scene on the given layer with the
		given cameras.
		Note that this may become ugly if the object is owned by
		another scene, be sure to remove it from there with `remove`
		(`keep=True`) beforehand.
		If no layer is supplied, will default to the first layer.
		If no cameras are supplied, will default to the default camera.
		"""
		self._members.append(obj)
		obj.set_context(self.get_context(layer, cameras))

	def remove(self, obj: SceneObject, keep: bool = False) -> None:
		"""
		Removes a scene object from this scene's registry.
		If `keep` is set to `True`, will not delete the removed object.
		If the object is unknown to the scene, does nothing.
		"""
		if obj in self._members:
			self._members.remove(obj)
			if keep:
				obj.invalidate_context()
			else:
				obj.delete()

	def update(self, dt: float) -> None:
		if self.game.debug:
			if self.game.raw_key_handler.just_pressed(R):
				logger.debug("hello")

			if self.game.raw_key_handler.just_pressed(B):
				print(self.batch.dump_debug_info())

		self._passed_time += dt
		self.clock.tick()

		self.effects.update(dt)

		for c in self.cameras.values():
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

		for camera in self.cameras.values():
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
				max(0, camera._height - CNST.GAME_HEIGHT), # glViewport is somehow lower-left
				#                                            origin oriented

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

	def get_context(
		self,
		layer_name: t.Optional[str] = None,
		camera_names: t.Optional[t.Union[str, t.Iterable[str]]] = None,
	) -> SceneContext:
		"""
		Returns a context for the given layer and camera names.
		Both may also be `None`, in which case the first layer or the
		first camera will be returned.
		"""
		if isinstance(camera_names, str):
			camera_names = (camera_names,)

		layer = self.default_layer if layer_name is None else self.layers[layer_name]
		cameras = (
			(self.default_camera,) if camera_names is None
			else tuple(self.cameras[cam] for cam in camera_names)
		)
		return SceneContext(self.batch, layer.get_group(), cameras)

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
				self._transition_in_cls.get_kernel(True, self.on_transition_in_complete)
			)

	def start_transition_out(self, new_scene_kernel: SceneKernel) -> None:
		"""
		Starts the "out" transition for a scene.
		"""
		if self._transition_out_cls is None:
			return

		self.game.push_scene(
			self._transition_out_cls.get_kernel(False, self.on_transition_out_complete)
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

		for cam in self.cameras.values():
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
		is_in: bool,
		on_end: t.Optional[t.Callable[["TransitionScene"], t.Any]] = None,
	) -> SceneKernel:
		return SceneKernel(cls, is_in, on_end)

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
