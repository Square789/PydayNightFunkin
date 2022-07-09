
from collections import OrderedDict
import typing as t

from loguru import logger
from pyglet.clock import Clock
from pyglet.gl import gl
from pyglet.window.key import B, R

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.pnf_player import SFXRing
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.scene_context import SceneContext
from pyday_night_funkin.core.scene_object import Container, SceneObject

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game

SceneObjectBound = t.TypeVar("SceneObjectBound", bound=SceneObject)


class Layer():
	"""
	Layer class over the given group.
	"""
	__slots__ = ("group", "force_order", "latest_order")

	def __init__(self, group: PNFGroup, force_order: bool) -> None:
		self.group = group
		self.force_order = force_order
		self.latest_order = 0

	def get_group(self, group_cls: t.Type[PNFGroup] = PNFGroup, *args, **kwargs) -> PNFGroup:
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
			kwargs["order"] = self.latest_order
			kwargs["parent"] = self.group
			self.latest_order += 1

			return group_cls(*args, **kwargs)
		else:
			return self.group


class BaseScene(Container):
	"""
	A scene holds a number of scene objects and cameras, functions to
	manipulate these in a way appropiate to the scene's nature and
	event handlers to call these functions.
	"""

	def __init__(self, game: "Game") -> None:
		"""
		Initializes the base scene.

		:param game: The `Game` the scene belongs to.
		"""
		super().__init__()

		self.game = game

		self.batch = PNFBatch()

		self.draw_passthrough = True
		self.update_passthrough = False

		self.layers = OrderedDict(
			(name, Layer(PNFGroup(order=i), force_order))
			for i, (name, force_order) in enumerate(
				(x, False) if not isinstance(x, tuple) else x
				for x in self.get_default_layers()
			)
		)
		if not self.layers:
			raise ValueError("Scenes must at least have one layer!")

		self._passed_time = 0.0
		self.clock = Clock(self._get_elapsed_time)

		# self._default_camera = Camera(-100, -100, CNST.GAME_WIDTH + 200, CNST.GAME_HEIGHT + 200)
		# self._default_camera.clear_color = (0.5, 0, 0, 1.0)
		# self._default_camera.x = -100
		# self._default_camera.y = -100
		self._default_camera = Camera(0, 0, CNST.GAME_WIDTH, CNST.GAME_HEIGHT)
		self.cameras = OrderedDict(
			(name, Camera(0, 0, w, h)) for name, w, h in (
				(x, CNST.GAME_WIDTH, CNST.GAME_HEIGHT) if not isinstance(x, tuple) else x
				for x in self.get_default_cameras()
			)
		)

		# Fails when nothing is added to a camera otherwise.
		for cam in (self._default_camera, *self.cameras):
			self.batch._get_draw_list(cam)

		self.sfx_ring = SFXRing()

	@staticmethod
	def get_default_cameras() -> t.Sequence[t.Union[str, t.Tuple[str, int, int]]]:
		"""
		Gets a list of the names to be used for this scene's cameras.
		Typically you'd use a main and a HUD/UI camera.
		"""
		return ()

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		"""
		Gets a list of layer names to be used for this scene.
		The layers can later be referenced by name in `create_object`.
		The layers will be drawn first-to-last as they are given.
		By default, the order in which drawables on the same layer
		are drawn is undefined. It's possible to force each
		drawable onto its own layer subgroup by specifying
		`("my_layer", True)` instead of just the layer name
		`"my_layer"`, which (probably) comes at a performance
		cost and prevents optimizations. This should be used
		only when necessary.
		"""
		return ()

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
		object_class: t.Type[SceneObjectBound],
		**kwargs,
	) -> SceneObjectBound:
		...

	# Everything is listed positionally, object_class is arg 3
	@t.overload
	def create_object(
		self,
		layer: t.Optional[str],
		cameras: t.Optional[t.Union[str, t.Iterable[str]]],
		object_class: t.Type[SceneObjectBound],
		*args,
		**kwargs,
	) -> SceneObjectBound:
		...

	# object_class is not given, return type is PNFSprite.
	@t.overload
	def create_object(
		self,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
		*args,
		**kwargs,
	) -> PNFSprite:
		...

	def create_object(
		self,
		layer: t.Optional[str] = None,
		cameras: t.Optional[t.Union[str, t.Iterable[str]]] = None,
		object_class: t.Type[SceneObjectBound] = PNFSprite,
		*args,
		**kwargs,
	) -> t.Union[SceneObjectBound, PNFSprite]:
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
		kwargs.setdefault("context", self.get_context(layer, cameras))
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
			if self.game.pyglet_ksh[R]:
				logger.debug("hello")

			if self.game.pyglet_ksh[B]:
				print(self.batch.dump_debug_info())

		self._passed_time += dt
		self.clock.tick()

		self._default_camera.update(dt)
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

		for camera in (self._default_camera, *self.cameras.values()):
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
		default camera will be returned.
		"""
		if isinstance(camera_names, str):
			camera_names = (camera_names,)
		layer = next(iter(self.layers.values())) if layer_name is None else self.layers[layer_name]
		cameras = (
			(self._default_camera,) if camera_names is None
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

	def on_subscene_removal(self, subscene, *args, **kwargs):
		"""
		Called whenever a direct subscene of this scene has
		`remove_scene` called on it.
		Offers a possibility for scenes to react to subscene removal.
		"""
		self.game.remove_scene(subscene)

	@t.final
	def delete(self) -> None:
		raise RuntimeError("To delete scenes, use `destroy`!")

	def destroy(self) -> None:
		"""
		Destroy the scene by deleting its members and graphics batch.
		**!** This does not remove the scene from the game's scene
		stack and will cause errors if used improperly.
		Chances are you want to use `remove_scene` instead.
		"""
		for x in self._members.copy():
			x.delete()
		self._members.clear()

		for cam in self.cameras.values():
			cam.delete()
		self._default_camera.delete()

		self.sfx_ring.delete()

		self.batch.delete()
		self.batch = None
		self.game = None # reference breaking or something
