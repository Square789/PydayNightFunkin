
import ctypes
from time import time
import typing as t

from pyglet import gl
from pyglet import graphics
from pyglet.image import AbstractImage, TextureArrayRegion
from pyglet.math import Vec2
from pyglet import sprite

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.tweens import TWEEN_ATTR
from pyday_night_funkin.graphics.pnf_animation import AnimationController, PNFAnimation
from pyday_night_funkin.graphics.shaders import (
	PNFSpriteVertexShader, PNFSpriteFragmentShader, ShaderContainer
)
from pyday_night_funkin.utils import clamp

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import UniformBufferObject
	from pyday_night_funkin.graphics.camera import Camera


EffectBound = t.TypeVar("EffectBound", bound="Effect")


_TWEEN_ATTR_NAME_MAP = {
	TWEEN_ATTR.X: "x",
	TWEEN_ATTR.Y: "y",
	TWEEN_ATTR.ROTATION: "rotation",
	TWEEN_ATTR.OPACITY: "opacity",
	TWEEN_ATTR.SCALE: "scale",
	TWEEN_ATTR.SCALE_X: "scale_x",
	TWEEN_ATTR.SCALE_Y: "scale_y",
}


class PNFSpriteGroup(sprite.SpriteGroup):
	def __init__(self, cam_ubo: "UniformBufferObject", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.cam_ubo = cam_ubo

	def set_state(self):
		self.program.use()
		self.cam_ubo.bind()

		gl.glActiveTexture(gl.GL_TEXTURE0)
		# gl.glTexParameteri(self.texture.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
		# gl.glTexParameteri(self.texture.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
		gl.glBindTexture(self.texture.target, self.texture.id)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(self.blend_src, self.blend_dest)

	def unset_state(self):
		gl.glDisable(gl.GL_BLEND)
		gl.glBindTexture(self.texture.target, 0)

		self.program.stop()


class Movement():
	__slots__ = ("velocity", "acceleration")
	
	def __init__(self, velocity: Vec2, acceleration: Vec2) -> None:
		self.velocity = velocity
		self.acceleration = acceleration

	# Dumbed down case of code shamelessly stolen from https://github.com/HaxeFlixel/
	# flixel/blob/e3c3b30f2f4dfb0486c4b8308d13f5a816d6e5ec/flixel/FlxObject.hx#L738
	def update(self, dt: float) -> Vec2:
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

		self.velocity = Vec2(vel_x, vel_y)

		return Vec2(posx_delta, posy_delta)


class Effect():
	"""
	"Abstract" effect class intertwined with the PNFSprite.
	"""
	def __init__(
		self,
		duration: float,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		if duration <= 0.0:
			raise ValueError("Duration may not be negative or zero!")

		self.on_complete = on_complete
		self.duration = duration
		self.cur_time = 0.0

	def update(self, dt: float, sprite: "PNFSprite") -> None:
		raise NotImplementedError("Subclass this")

	def is_finished(self) -> bool:
		return self.cur_time >= self.duration


class Tween(Effect):
	def __init__(
		self,
		tween_func: t.Callable,
		attr_map: t.Dict[str, t.Tuple[t.Any, t.Any]],
		duration: float,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		super().__init__(duration, on_complete)
		self.tween_func = tween_func
		self.attr_map = attr_map

	def update(self, dt: float, sprite: "PNFSprite") -> None:
		self.cur_time += dt
		progress = self.tween_func(clamp(self.cur_time, 0, self.duration) / self.duration)

		for attr_name, (v_ini, v_diff) in self.attr_map.items():
			setattr(sprite, attr_name, v_ini + v_diff * progress)


class Flicker(Effect):
	def __init__(
		self,
		interval: float,
		start_visibility: bool,
		end_visibility: bool,
		duration: float,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		super().__init__(duration, on_complete)
		if interval <= 0.0:
			raise ValueError("Interval may not be negative or zero!")

		self.interval = interval
		self.end_visibility = end_visibility
		self._next_toggle = interval
		self._visible = start_visibility

	def update(self, dt: float, sprite: "PNFSprite") -> None:
		self.cur_time += dt
		if self.is_finished():
			sprite.visible = self.end_visibility
			return

		if self.cur_time >= self._next_toggle:
			while self.cur_time >= self._next_toggle:
				self._next_toggle += self.interval
			self._visible = not self._visible
			sprite.visible = self._visible


class PNFSprite(sprite.Sprite):
	"""
	TODO doc

	WARNING: This subclass meddles with many underscore-prepended
	attributes of the standard pyglet Sprite, which may completely
	break it in any other pyglet releases.
	Also, it breaks pyglet's animation events.
	"""

	shader_container = ShaderContainer(
		PNFSpriteVertexShader.generate(),
		PNFSpriteFragmentShader.generate(),
	)

	def __init__(
		self,
		camera: "Camera",
		image: t.Optional[AbstractImage] = None,
		x = 0,
		y = 0,
		blend_src = gl.GL_SRC_ALPHA,
		blend_dest = gl.GL_ONE_MINUS_SRC_ALPHA,
		batch = None,
		group = None,
		usage = "dynamic",
		subpixel = False,
		program = None,
	) -> None:
		image = CNST.ERROR_TEXTURE if image is None else image

		self.animation = AnimationController()
		self.camera = camera

		self.movement: t.Optional[Movement] = None
		self.effects: t.List[EffectBound] = []

		self._x = x
		self._y = y
		self._scroll_factor = (1.0, 1.0)

		self._texture = image.get_texture()

		if isinstance(image, TextureArrayRegion):
			raise NotImplementedError("What's the deal with TextureArrayRegions?")
			program = sprite.get_default_array_shader()
		else:
			program = self.shader_container.get_program()

		self._batch = batch or graphics.get_default_batch()
		self._group = PNFSpriteGroup(
			self.camera.ubo, self._texture, blend_src, blend_dest, program, parent=group
			)
		self._usage = usage
		self._subpixel = subpixel
		self._create_vertex_list()

		self.image = image

	def _create_vertex_list(self):
		usage = self._usage
		self._vertex_list = self._batch.add_indexed(
			4, gl.GL_TRIANGLES, self._group, [0, 1, 2, 0, 2, 3],
			"position2f/" + usage,
			("colors4Bn/" + usage, (*self._rgb, int(self._opacity)) * 4),
			("translate2f/" + usage, (self._x, self._y) * 4),
			("scale2f/" + usage,
				(self._scale * self._scale_x, self._scale * self._scale_y) * 4),
			("rotation1f/" + usage, (self._rotation, ) * 4),
			("scroll_factor2f/" + usage, self._scroll_factor * 4),
			("tex_coords3f/" + usage, self._texture.tex_coords),
		)
		self._update_position()

	def screen_center(self, screen_dims: Vec2, x: bool = True, y: bool = True) -> None:
		"""
		Sets the sprite's world position so that it is centered 
		on screen. (Ignoring camera and scroll factors)
		`x` and `y` can be set to false to only center the sprite
		along one of the axes.
		"""
		if x:
			self.x = (screen_dims[0] - self.width) // 2
		if y:
			self.y = (screen_dims[1] - self.height) // 2

	def get_midpoint(self) -> Vec2:
		"""
		Returns the middle point of this sprite, based on its current
		texture and world position.
		"""
		return Vec2(
			self._x + self.signed_width * 0.5,
			self._y + self.signed_height * 0.5,
		)

	def start_tween(
		self,
		tween_func: t.Callable[[float], float],
		attributes: t.Dict[TWEEN_ATTR, t.Any],
		duration: float,
		on_complete: t.Callable[[], t.Any] = None,
	) -> Tween:
		"""
		# TODO write some very cool doc
		"""
		# 0: initial value; 1: difference
		attr_map = {}
		for attribute, target_value in attributes.items():
			attribute_name = _TWEEN_ATTR_NAME_MAP[attribute]
			initial_value = getattr(self, attribute_name)
			attr_map[attribute_name] = (initial_value, target_value - initial_value)

		t = Tween(
			tween_func,
			duration = duration,
			attr_map = attr_map,
			on_complete = on_complete,
		)
		self.effects.append(t)
		return t

	def start_flicker(
		self,
		duration: float,
		interval: float,
		end_visibility: bool = True,
		on_complete: t.Callable[[], t.Any] = None,
	) -> Flicker:
		f = Flicker(
			interval = interval,
			start_visibility = self.visible,
			end_visibility = end_visibility,
			duration = duration,
			on_complete = on_complete,
		)
		self.effects.append(f)
		return f

	def start_movement(
		self,
		velocity: t.Union[Vec2, t.Tuple[float, float]],
		acceleration: t.Optional[t.Union[Vec2, t.Tuple[float, float]]] = None,
	) -> None:
		if not isinstance(velocity, Vec2):
			velocity = Vec2(*velocity)

		if acceleration is not None and not isinstance(acceleration, Vec2):
			acceleration = Vec2(*acceleration)

		self.movement = Movement(velocity, acceleration)

	def stop_movement(self) -> None:
		self.movement = None

	def check_animation_controller(self):
		"""
		Tests animation controller for new textures or offsets
		and applies them to the sprite.
		Useful for when waiting for `update_sprite` isn't possible during
		setup which i.e. depends on the first frame of an animation.
		"""
		if (new_frame := self.animation.query_new_texture()) is not None:
			self._set_texture(new_frame)

		if (new_offset := self.animation.query_new_offset()) is not None:
			self.update(
				x = self._x + (new_offset[0] * self._scale * self._scale_x),
				y = self._y + (new_offset[1] * self._scale * self._scale_y),
			)

	# Unfortunately, the name `update` clashes with sprite, so have
	# this as a certified code smell
	def update_sprite(self, dt: float) -> None:
		if self.animation.is_set:
			self.animation.update(dt)
			self.check_animation_controller()

		if self.movement is not None:
			dx, dy = self.movement.update(dt)
			self.update(x = self.x + dx, y = self.y + dy)

		finished_effects = []
		for effect in self.effects:
			effect.update(dt, self)
			if effect.is_finished():
				finished_effects.append(effect)

		for effect in finished_effects:
			if effect.on_complete is not None:
				effect.on_complete()
			try:
				self.effects.remove(effect)
			except ValueError:
				pass

	@property
	def scroll_factor(self) -> t.Tuple[float, float]:
		return self._scroll_factor

	@scroll_factor.setter
	def scroll_factor(self, new_sf: t.Tuple[float, float]) -> None:
		self._scroll_factor = new_sf
		self._vertex_list.scroll_factor[:] = new_sf * 4

	# @property
	# def width(self) -> float:
	# 	return abs(self.signed_width)

	# @property
	# def height(self):
	# 	return abs(self.signed_height)

	# @property
	# def signed_width(self) -> float:
	# 	if self.animation.is_set:
	# 		return self.animation.current_frame.frame_info[2]
	# 	return self._texture.width * self._scale_x * self._scale

	# @property
	# def signed_height(self) -> float:
	# 	if self.animation.is_set:
	# 		return self.animation.current_frame.frame_info[3]
	# 	return self._texture.height * self._scale_y * self._scale

	@property
	def signed_width(self) -> float:
		return self._texture.width * self._scale_x * self._scale
	@property
	def signed_height(self) -> float:
		return self._texture.height * self._scale_y * self._scale
	@property
	def image(self) -> t.Union[PNFAnimation, AbstractImage]:
		if self.animation.is_set:
			return self.animation.current
		return self._texture

	@image.setter
	def image(self, image: t.Union[PNFAnimation, AbstractImage]) -> None:
		if isinstance(image, PNFAnimation):
			raise RuntimeError(
				"Please play animations via the sprite's animation controller: "
				"`sprite.animation.play()`"
			)

		self.animation.stop()
		self._set_texture(image.get_texture())

	def _animate(self, dt: float) -> None:
		raise RuntimeError(
			"For PNFSprites and its subclasses, the animation controller must "
			"be used instead of pyglet's clock-based animation!"
		)

	# === Below methods are largely copy-pasted from the superclass sprite === #

	def _set_texture(self, texture):
		prev_h, prev_w = self._texture.height, self._texture.width
		if texture.id is not self._texture.id:
			self._group = PNFSpriteGroup(
				self.camera.ubo, texture, self._group.blend_src, self._group.blend_dest,
				self._group.program, 0, self._group.parent
			)
			self._vertex_list.delete()
			self._texture = texture
			self._create_vertex_list()
		else:
			self._vertex_list.tex_coords[:] = texture.tex_coords
		self._texture = texture
		# If this is not done, screws over vertices if the texture changes
		# dimension thanks to top left coords
		if prev_h != texture.height or prev_w != texture.width:
			self._update_position()

	def _update_position(self):
		# Contains some manipulations to creation to the
		# vertex array since otherwise it would be displayed
		# upside down
		if not self._visible:
			self._vertex_list.position[:] = (0, 0, 0, 0, 0, 0, 0, 0)
		else:
			img = self._texture
			x1 = -img.anchor_x
			y1 = -img.anchor_y + img.height
			x2 = -img.anchor_x + img.width
			y2 = -img.anchor_y

			if self._subpixel:
				self._vertex_list.position[:] = (x1, y1, x2, y1, x2, y2, x1, y2)
			else:
				self._vertex_list.position[:] = tuple(map(int, (x1, y1, x2, y1, x2, y2, x1, y2)))
