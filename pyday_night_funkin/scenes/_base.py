
from collections import OrderedDict
import typing as t

from loguru import logger
from pyglet.clock import Clock
from pyglet.window.key import B, R, Y

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.scene_object import Container, SceneObject
from pyday_night_funkin.sfx_ring import SFXRing

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.types import PNFSpriteBound


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
	A scene holds a number of sprites and cameras, functions to
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
		self.creation_args = None
		self.batch = PNFBatch()

		self.draw_passthrough = True
		self.update_passthrough = False

		self.layers = OrderedDict(
			(name, Layer(PNFGroup(order=i), force_order))
			for i, (name, force_order) in enumerate(
				(x, False) if not isinstance(x, tuple) else x
				for x in self.get_layer_names()
			)
		)
		if not self.layers:
			raise ValueError("Scenes must at least have one layer!")

		self._passed_time = 0.0
		self.clock = Clock(self._get_elapsed_time)

		self._default_camera = Camera()
		self.cameras = {name: Camera() for name in self.get_camera_names()}

		self.sfx_ring = SFXRing(CNST.SFX_RING_SIZE)

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		"""
		Gets a list of the names to be used for this scene's cameras.
		Typically you'd use a main and a HUD/UI camera.
		"""
		return ()

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		"""
		Gets a list of layer names to be used for this scene.
		The layers can later be referenced by name in `create_sprite`.
		The layers will be drawn first-to-last as they are given.
		By default, the order in which sprites on the same layer
		are drawn is undefined. It's possible to force each
		sprite onto its own layer subgroup by specifying
		`("my_layer", True)` instead of just the layer name
		`"my_layer"`, which (probably) comes at a performance
		cost and prevents optimizations. This should be used
		only when necessary.
		"""
		return ()

	def _get_elapsed_time(self) -> float:
		return self._passed_time

	def create_sprite(
		self,
		layer: t.Optional[str] = None,
		camera: t.Optional[str] = None,
		sprite_class: t.Type["PNFSpriteBound"] = PNFSprite,
		*args,
		**kwargs,
	) -> "PNFSpriteBound":
		"""
		Creates a sprite on the given layer belonging to a camera.
		If a camera name is specified (and the camera exists in the
		scene), the sprite will be registered with it and its
		transformations immediatedly applied. If no camera name is
		specified, the sprite will be attached to a default camera
		that is never moved.
		The sprite class will be created with all args and kwargs,
		as well as a fitting `context` filled in by the scene
		if not otherwise given. (And if you give it another one, you
		better know what you're doing.)
		"""
		kwargs.setdefault("context", self.get_context(layer))
		kwargs.setdefault(
			"camera",
			self._default_camera if camera is None else self.cameras[camera]
		)

		sprite = sprite_class(*args, **kwargs)

		self._members.add(sprite)

		return sprite

	def set_context(self, _: Context) -> None:
		raise RuntimeError("Can't set a scene's context, it's the scene hierarchy root!")

	def invalidate_context(self) -> None:
		raise RuntimeError("Can't invalidate a scene's context; try `remove_scene` instead!")

	def add(self, obj: SceneObject, layer: t.Optional[str] = None):
		"""
		Add a SceneObject to the scene on the given layer.
		If no layer is supplied, will default to the first layer.
		"""
		self._members.add(obj)
		obj.set_context(self.get_context(layer))

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
				self.batch._dump_draw_list()

		self._passed_time += dt
		self.clock.tick()

		self._default_camera.update(dt)
		for c in self.cameras.values():
			c.update(dt)

		for x in self._members.copy():
			x.update(dt)

	def draw(self) -> None:
		"""
		Draw the scene.
		There should be no reason to override this.
		"""
		self.batch.draw()

	def get_context(self, layer: t.Optional[str] = None) -> Context:
		"""
		Returns a context for the given layer. # TODO or none bla bla
		"""
		return Context(self.batch, self.get_layer(layer).get_group())

	def get_layer(self, layer: t.Optional[str] = None) -> Layer:
		return next(iter(self.layers.values())) if layer is None else self.layers[layer]

	def remove_scene(self, *args, **kwargs) -> None:
		"""
		Removes this scene by telling the below scene, or the game if
		this scene is the parent scene, to remove it.
		All args and kwargs will be passed through to a parent scene's
		`remove_subscene` method, but ignored if the game receives the
		removal request.
		"""
		remover = self.game.get_previous_scene(self)
		if remover is None:
			self.game.remove_scene(self)
		else:
			remover.remove_subscene(*args, **kwargs)

	def remove_subscene(self, *args, **kwargs):
		"""
		Called by the scene above's `remove_scene` method.
		"""
		subscene = self.game.get_next_scene(self)
		self.game.remove_scene(subscene)

	def destroy(self) -> None:
		"""
		Destroy the scene by deleting its sprites and graphics batch.
		**!** This does not remove the scene from the game's scene
		stack and will cause errors if used improperly.
		Chances are you want to use `remove_scene` instead.
		"""
		for x in self._members.copy():
			x.delete()
		self._members.clear()

		del self.batch
		del self.game # reference breaking or something
