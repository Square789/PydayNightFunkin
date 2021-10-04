
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
import pyglet.clock
from pyglet.graphics import Group
from pyglet.window.key import B, R

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.graphics.camera import Camera
from pyday_night_funkin.graphics.pnf_sprite import PNFSprite
from pyday_night_funkin.sfx_ring import SFXRing
from pyday_night_funkin.utils import clamp
from pyday_night_funkin.tweens import TWEEN_ATTR

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


T = t.TypeVar("T", bound = PNFSprite)


_TWEEN_ATTR_NAME_MAP = {
	TWEEN_ATTR.X: "x",
	TWEEN_ATTR.Y: "y",
	TWEEN_ATTR.ROTATION: "rotation",
	TWEEN_ATTR.OPACITY: "opacity",
	TWEEN_ATTR.SCALE: "scale",
	TWEEN_ATTR.SCALE_X: "scale_x",
	TWEEN_ATTR.SCALE_Y: "scale_y",
}


class _MovementInfo():
	__slots__ = ("velocity", "acceleration")
	
	def __init__(
		self,
		velocity: t.Tuple[float, float] = (0.0, 0.0),
		acceleration: t.Tuple[float, float] = (0.0, 0.0),
	) -> None:
		self.velocity = velocity
		self.acceleration = acceleration

	# Dumbed down case of code shamelessly stolen from https://github.com/HaxeFlixel/
	# flixel/blob/e3c3b30f2f4dfb0486c4b8308d13f5a816d6e5ec/flixel/FlxObject.hx#L738
	def update(self, dt: float) -> t.Tuple[float, float]:
		acc_x, acc_y = self.acceleration
		vel_x, vel_y = self.velocity

		vel_delta = 0.5 * acc_x * dt
		vel_x += vel_delta
		posx_delta = vel_x * dt
		vel_x += vel_delta

		vel_delta = 0.5 * acc_y * dt
		vel_y += vel_delta
		posy_delta = vel_y * dt
		vel_y += vel_delta

		self.velocity = (vel_x, vel_y)

		return (posx_delta, posy_delta)


class _TweenInfo():
	__slots__ = (
		"tween_func", "start_time", "stop_time", "time_difference", "cur_time",
		"attr_map", "on_complete"
	)

	def __init__(
		self,
		tween_func: t.Callable,
		start_time: float,
		stop_time: float,
		time_difference: float,
		cur_time: float,
		attr_map: t.Dict[str, t.Tuple[t.Any, t.Any]],
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		self.tween_func = tween_func
		self.start_time = start_time
		self.stop_time = stop_time
		self.time_difference = time_difference
		self.cur_time = cur_time
		self.attr_map = attr_map
		self.on_complete = on_complete

	def update(self, dt: float) -> t.Dict[str, t.Any]:
		self.cur_time += dt
		progress = (
			clamp(self.cur_time, self.start_time, self.stop_time) - self.start_time
		) / self.time_difference

		return {
			attr_name: v_ini + v_diff * self.tween_func(progress)
			for attr_name, (v_ini, v_diff) in self.attr_map.items()
		}

	def is_finished(self) -> bool:
		return self.cur_time >= self.stop_time


class _SpriteInfo():
	__slots__ = ("movement", "tweens")

	def __init__(self) -> None:
		self.movement = None
		self.tweens = {}

	def set_movement(self, sprite_movement: t.Optional[_MovementInfo]) -> None:
		self.movement = sprite_movement

	def set_tween(self, tween: _TweenInfo) -> None:
		self.tweens[id(tween)] = tween

	def remove_tween(self, tween_identifier: int) -> None:
		if self.tweens is not None and tween_identifier in self.tweens:
			self.tweens.pop(tween_identifier)


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

	def __init__(
		self,
		game: "Game",
	) -> None:
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
		self._sprite_info: t.Dict[PNFSprite, t.Optional[_SpriteInfo]] = {}
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

		self._sprite_info[sprite] = None

		return sprite

	def remove_sprite(self, sprite: PNFSprite) -> None:
		"""
		Removes a sprite from this scene's sprite registry and deletes
		it.
		If the sprite is unknown to the scene, does nothing.
		"""
		if sprite in self._sprite_info:
			self._sprite_info.pop(sprite)
			sprite.delete()

	def start_movement(
		self,
		sprite: PNFSprite,
		velocity: t.Tuple[float, float],
		acceleration: t.Tuple[float, float] = (0.0, 0.0),
	) -> None:
		if sprite not in self._sprite_info:
			return

		if self._sprite_info[sprite] is None:
			self._sprite_info[sprite] = _SpriteInfo()

		self._sprite_info[sprite].set_movement(_MovementInfo(velocity, acceleration))

	def stop_movement(self, sprite: PNFSprite) -> None:
		if sprite not in self._sprite_info:
			return

		self._sprite_info[sprite].movement = None

	def start_tween(
		self,
		sprite: PNFSprite,
		tween_func: t.Callable[[float], float],
		attributes: t.Dict[TWEEN_ATTR, t.Any],
		duration: float,
		on_complete: t.Callable[[], t.Any] = None,
		start_delay: float = 0.0,
	) -> int:
		"""
		# TODO write some very cool doc
		"""
		if start_delay < 0.0:
			raise ValueError("Can't start a tween in the past!")

		if sprite not in self._sprite_info:
			return

		if start_delay:
			pyglet.clock.schedule_once(
				lambda _: self.start_tween(sprite, tween_func, attributes, duration, on_complete),
				start_delay,
			)
			return

		# 0: initial value; 1: difference
		attr_map = {}
		for attribute, target_value in attributes.items():
			attribute_name = _TWEEN_ATTR_NAME_MAP[attribute]
			initial_value = getattr(sprite, attribute_name)
			attr_map[attribute_name] = (initial_value, target_value - initial_value)

		start_time = time()

		if self._sprite_info[sprite] is None:
			self._sprite_info[sprite] = _SpriteInfo()

		ti = _TweenInfo(
			tween_func,
			start_time = start_time,
			stop_time = start_time + duration,
			time_difference = duration,
			cur_time = start_time,
			attr_map = attr_map,
			on_complete = on_complete,
		)

		self._sprite_info[sprite].set_tween(ti)

		return id(ti)

	def stop_tween(self, sprite: PNFSprite, tween_ident: int):
		i = self._sprite_info.get(sprite, None)
		if i is None:
			return

		i.remove_tween(tween_ident)

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

		finished_tweens = []
		for sprite, info in self._sprite_info.items():
			if info is None:
				continue

			if info.movement is not None:
				dx, dy = info.movement.update(dt)
				sprite.update(
					x = sprite.x + dx,
					y = sprite.y + dy,
				)

			for tween in info.tweens.values():
				for attr, v in tween.update(dt).items():
					setattr(sprite, attr, v)
				# on_complete can do crazy stuff, handle
				# outside to prevent "dict changed size during iteration" etc.
				if tween.is_finished():
					finished_tweens.append((sprite, tween))

		for sprite, tween in finished_tweens:
			if tween.on_complete is not None:
				# NOTE: It's ok for a callback to switch scenes and stuff,
				# even this may not be safe enough
				tween.on_complete()
			self.stop_tween(sprite, id(tween))

	def draw(self) -> None:
		self.batch.draw()
