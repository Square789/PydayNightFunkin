
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
from pyglet.clock import Clock
from pyglet.graphics import Batch, Group
from pyglet.window.key import B, R

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.graphics import Camera, PNFSprite
from pyday_night_funkin.graphics.pnf_sprite_container import Layer
from pyday_night_funkin.graphics.scene_object import Container
from pyday_night_funkin.sfx_ring import SFXRing

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.types import PNFSpriteBound


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
		self.game = game

		self.creation_args = None

		self.batch = Batch()

		self.draw_passthrough = True
		self.update_passthrough = False

		self.layers = OrderedDict(
			(name, Layer(Group(order = i), force_order))
			for i, (name, force_order) in enumerate(
				(x, False) if not isinstance(x, tuple) else x
				for x in self.get_layer_names()
			)
		)

		self._passed_time = 0.0
		self.clock = Clock(self._get_elapsed_time)

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

	def _get_elapsed_time(self) -> float:
		return self._passed_time

	def create_sprite(
		self,
		layer: str,
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

		for sprite in self._sprites.copy():
			sprite.update(dt)

	def draw(self) -> None:
		"""
		Draw the scene.
		There should be no reason to override this.
		"""
		self.batch.draw()

	def remove(self, *args, **kwargs) -> None:
		"""
		Removes a scene by telling the below scene, or the game if
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
		Called by the scene above's `remove` method.
		"""
		subscene = self.game.get_next_scene(self)
		self.game.remove_scene(subscene)

	def destroy(self) -> None:
		"""
		Destroy the scene by deleting its sprites and graphics batch.
		**!** This does not remove the scene from the game's scene
		stack and will cause errors if used improperly.
		Chances are you want to use `remove` instead.
		"""
		for spr in self._sprites.copy():
			spr.delete()
		self._sprites.clear()

		del self.batch
		del self.game # reference breaking or something
