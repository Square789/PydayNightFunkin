
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
from pyglet.graphics import Group
from pyglet.window.key import B, R

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.graphics.camera import Camera
from pyday_night_funkin.graphics.pnf_sprite import PNFSprite
from pyday_night_funkin.sfx_ring import SFXRing

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


T = t.TypeVar("T", bound = PNFSprite)


class Layer():
	"""
	Layer class over the given group.
	"""
	__slots__ = ("group", "force_order", "latest_order")

	def __init__(self, group: Group, force_order: bool) -> None:
		self.group = group
		self.force_order = force_order
		self.latest_order = 0

	def get_group(self, group_cls: t.Optional[t.Type[Group]] = None, *args, **kwargs) -> Group:
		"""
		Returns a group to attach an object to on this layer.

		A layer with forced order will create and return an
		incrementally ordered subgroup with the layer's group as its
		parent.
		A layer without forced order will simply return its own group.
		"""
		# NOTE: Not really relevant in practice, but the order will
		# keep increasing ad infinitum, I don't like that a lot
		if self.force_order:
			if group_cls is None:
				group_cls = Group
			kwargs["order"] = self.latest_order
			kwargs["parent"] = self.group
			self.latest_order += 1

			return group_cls(*args, **kwargs)
		else:
			return self.group

class BaseScene():
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
		self.game = game
		self.batch = game.main_batch

		self.layers = OrderedDict(
			(name, Layer(Group(order = i), force_order))
			for i, (name, force_order) in enumerate(
				(x, False) if not isinstance(x, tuple) else x
				for x in self.get_layer_names()
			)
		)

		self._default_camera = Camera()
		self.cameras = {name: Camera() for name in self.get_camera_names()}

		self._sprites: t.Set[PNFSprite] = set()

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

	def create_sprite(
		self,
		layer: str,
		camera: t.Optional[str] = None,
		sprite_class: t.Type[T] = PNFSprite,
		*args,
		**kwargs,
	) -> T:
		"""
		Creates a sprite on the given layer belonging to a camera.
		If a camera name is specified (and the camera exists in the
		scene), the sprite will be registered with it and its
		transformations immediatedly applied. If no camera name is
		specified, the sprite will be attached to a default camera
		that is never moved.
		The sprite class will be created with all args and kwargs,
		as well as a fitting `batch` and `group` filled in by the scene
		if not otherwise given. (And if you give it another batch or
		group you better know what you're doing.)
		"""
		kwargs.setdefault("batch", self.batch)
		kwargs.setdefault("group", self.layers[layer].get_group())
		kwargs.setdefault("camera", self._default_camera if camera is None else self.cameras[camera])

		sprite = sprite_class(*args, **kwargs)

		self._sprites.add(sprite)

		return sprite

	def remove_sprite(self, sprite: PNFSprite) -> None:
		"""
		Removes a sprite from this scene's sprite registry and deletes
		it.
		If the sprite is unknown to the scene, does nothing.
		"""
		if sprite in self._sprites:
			self._sprites.remove(sprite)
			sprite.delete()

	def on_leave(self) -> None:
		"""
		Called when scene is about to be switched away from.
		"""
		pass

	def on_window_resize(self, new_w: int, new_h: int) -> None:
		"""
		Called when the game window is resized.
		"""
		pass

	def update(self, dt: float) -> None:
		if self.game.debug:
			if self.game.pyglet_ksh[R]:
				logger.debug("hello")

			if self.game.pyglet_ksh[B]:
				self.batch._dump_draw_list()

		self._default_camera.update(dt)
		for c in self.cameras.values():
			c.update(dt)

		for sprite in set(self._sprites):
			sprite.update_sprite(dt)

	def draw(self) -> None:
		self.batch.draw()
