
from enum import IntEnum
from pyday_night_funkin.tweens import TWEEN, TWEENS
from time import time
import typing as t

import pyglet.clock
from pyglet.gl import GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA
from pyglet.image import AbstractImage
from pyglet.image.animation import Animation
from pyglet.shapes import Line
from pyglet.sprite import Sprite
from pyglet.text import Label

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.utils import clamp

if t.TYPE_CHECKING:
	from pyglet.image import Texture
	from pyday_night_funkin.image_loader import FrameInfoTexture
	from pyday_night_funkin.camera import Camera


class TWEEN_ATTR(IntEnum):
	X = 0
	Y = 1
	ROTATION = 2
	OPACITY = 3
	SCALE = 4
	SCALE_X = 5
	SCALE_Y = 6


_TWEEN_ATTR_NAME_MAP = {
	TWEEN_ATTR.X: "_world_x",
	TWEEN_ATTR.Y: "_world_y",
	TWEEN_ATTR.ROTATION: "_world_rotation",
	TWEEN_ATTR.OPACITY: "_world_opacity",
	TWEEN_ATTR.SCALE: "_world_scale",
	TWEEN_ATTR.SCALE_X: "_world_scale_x",
	TWEEN_ATTR.SCALE_Y: "_world_scale_y",
}


class OffsetAnimationFrame():
	"""
	Similar to pyglet's AnimationFrame, except it also stores a
	per-frame offset that should be applied to its receiving sprite's
	x and y coordinates as well as a name that can be used to identify
	the frame.
	"""

	__slots__ = ("image", "duration", "frame_info", "name")

	def __init__(
		self,
		image: "Texture",
		duration: float,
		frame_info: t.Tuple[int, int, int, int],
		name: str = "?"
	) -> None:
		self.image = image
		self.duration = duration
		self.frame_info = frame_info
		self.name = name

	def __repr__(self):
		return (
			f"AnimationFrame({self.image}, duration={self.duration}, "
			f"frame_info={self.frame_info})"
		)


class PNFAnimation(Animation):
	"""
	Subclasses the pyglet Animation to add the information whether it
	should be looped into it.
	"""
	def __init__(self, frames: t.Sequence[OffsetAnimationFrame], loop: bool = False):
		super().__init__(frames)
		self.loop = loop


class PNFSprite(Sprite):
	"""
	TODO doc

	IMPORTANT: If you want to move, scale or rotate this sprite, be
	sure to modify i.e. its `world_x` and NOT its `x` attribute,
	otherwise you will directly modify screen coordinates which is sure
	to mess up when any amount of camera movement is involved.

	WARNING: This subclass meddles with many underscore-prepended
	attributes of the standard pyglet Sprite, which may completely
	break it in any other pyglet releases.
	"""
	def __init__(
		self,
		image: t.Optional[t.Union[PNFAnimation, AbstractImage]] = None,
		x: int = 0,
		y: int = 0,
		blend_src = GL_SRC_ALPHA,
		blend_dest = GL_ONE_MINUS_SRC_ALPHA,
		batch = None,
		group = None,
		usage = "dynamic",
		subpixel = False,
	) -> None:

		if image is None:
			image = CNST.ERROR_TEXTURE

		super().__init__(image, 0, 0, blend_src, blend_dest, batch, group, usage, subpixel)

		self._animations = {}
		self._animation_offset = (0, 0)
		self.camera: t.Optional["Camera"] = None
		# The `world_` variables below are meant to hold the sprite's position
		# (top left because lmao), scale and rotation non-influenced by any camera operations
		# that may modify them for the actual rendering superclass sprite's set of these variables.
		self._world_x = x
		self._world_y = y
		self._world_rotation = 0
		self._world_opacity = 255
		self._world_scale = 1.0
		self._world_scale_x = 1.0
		self._world_scale_y = 1.0
		self._scroll_factor = (1.0, 1.0)

	def _animate(self, dt: float) -> None:
		# Disgusting override of underscore method, required to set the
		# sprite's position on animation.
		super()._animate(dt)
		fx, fy = frame_offset = self._animation.frames[self._frame_index].frame_info[0:2]
		if frame_offset != self._animation_offset:
			cfx, cfy = self._animation_offset
			self._world_x += cfx
			self._world_x -= fx
			self._world_y += cfy
			self._world_y -= fy
			self._animation_offset = frame_offset
			self.update_camera()

	def add_animation(
		self,
		name: str,
		anim_data: t.Union[PNFAnimation, t.Sequence["FrameInfoTexture"]],
		fps: float = 24.0,
		loop: bool = False
	) -> None:
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		spf = 1.0 / fps
		if isinstance(anim_data, PNFAnimation):
			self._animations[name] = anim_data
		else:
			self._animations[name] = PNFAnimation(
				[OffsetAnimationFrame(tex.texture, spf, tex.frame_info, name) for tex in anim_data], loop
			)

	# def get_debug_rect(
	# 	self,
	# 	width:int = 1,
	# 	color: t.Tuple[int, int, int] = (255, 255, 255),
	# 	batch: "Batch" = None,
	# 	group: "Group" = None
	# ) -> t.Tuple[Line, Line, Line, Line, Label, Label]:
	# 	"""
	# 	Returns a 6-Tuple of 4 lines surrounding this sprite as
	# 	dictated by its screen `x`, `y`, `width` and `height`
	# 	properties and two labels describing these coordinates,
	# 	one for screen values, one for the world position.
	# 	"""
	# 	x, y, w, h = self.x, self.y, self.width, self.height
	# 	wx, wy = self.world_x, self.world_y
	# 	return (
	# 		Line(x, y + h, x + w, y + h, width, color, batch, group),
	# 		Line(x + w, y + h, x + w, y, width, color, batch, group),
	# 		Line(x + w, y, x, y, width, color, batch, group),
	# 		Line(x, y, x, y + h, width, color, batch, group),
	# 		# LABELS ARE INSANELY EXPENSIVE!!!
	# 		# (Well i guess creating them every single frame is)
	# 		Label(
	# 			f"S X:{x} Y:{y} W:{w} H:{h}",
	# 			font_name = "Consolas",
	# 			font_size = 12,
	# 			x = x,
	# 			y = y + h - 12,
	# 			batch = batch
	# 		),
	# 		Label(
	# 			f"W X:{wx} Y:{wy}",
	# 			font_name = "Consolas",
	# 			font_size = 12,
	# 			x = x,
	# 			y = y + h - 26,
	# 			batch = batch
	# 		),
	# 	)

	def update_camera(self):
		if self.camera is not None:
			self.camera.apply_camera_attributes(self)

	def play_animation(self, name: str) -> None:
		self.image = self._animations[name]

	def tween(
		self,
		tween_type: TWEEN,
		attribute: TWEEN_ATTR,
		target_value: t.Union[int, float],
		duration: float,
		on_complete: t.Callable = None,
	) -> None:
		"""
		# TODO write some very cool doc
		"""
		attr_name = _TWEEN_ATTR_NAME_MAP[attribute]
		start_time = time()
		stop_time = start_time + duration
		time_difference = stop_time - start_time
		initial_value = getattr(self, attr_name)
		value_difference = target_value - initial_value
		tween_func = TWEENS[tween_type]
		cur_time = start_time

		# NOTE: maybe implement multiple attribute tweening later
		def tween_schedule_func(dt: float):
			nonlocal cur_time
			cur_time += dt
			progress = (clamp(cur_time, start_time, stop_time) - start_time) / time_difference
			setattr(self, attr_name, initial_value + (value_difference * tween_func(progress)))
			self.update_camera()
			if cur_time >= stop_time:
				pyglet.clock.unschedule(tween_schedule_func)
				if on_complete is not None:
					on_complete()

		pyglet.clock.schedule(tween_schedule_func)

	def world_update(self,
		x: int = None,
		y: int = None,
		rotation: float = None,
		opacity: int = None,
		scale: float = None,
		scale_x: float = None,
		scale_y: float = None,
		scroll_factor: t.Tuple[int, int] = None,
	):
		"""
		Updates multiple attributes at once and only pokes a
		potentially associated camera once to update them all.
		"""
		if x is not None:
			self._world_x = x
		if y is not None:
			self._world_y = y
		if rotation is not None:
			self._world_rotation = rotation
		if opacity is not None:
			self._world_opacity = opacity
		if scale is not None:
			self._world_scale = scale
		if scale_x is not None:
			self._world_scale_x = scale_x
		if scale_y is not None:
			self._world_scale_y = scale_y
		if scroll_factor is not None:
			self._scroll_factor = scroll_factor
		self.update_camera()

	# PNFSprite properties

	@property
	def scroll_factor(self) -> t.Tuple[float, float]:
		return self._scroll_factor

	@scroll_factor.setter
	def scroll_factor(self, new_sf: t.Tuple[float, float]) -> None:
		self._scroll_factor = new_sf
		self.update_camera()

	@property
	def world_x(self) -> int:
		return self._world_x

	@world_x.setter
	def world_x(self, new_x: int) -> None:
		self._world_x = new_x
		self.update_camera()

	@property
	def world_y(self) -> int:
		return self._world_y

	@world_y.setter
	def world_y(self, new_y: int) -> None:
		self._world_y = new_y
		self.update_camera()

	@property
	def world_rotation(self) -> float:
		return self._world_rotation

	@world_rotation.setter
	def world_rotation(self, new_rot: float) -> None:
		self._world_rotation = new_rot
		self.update_camera()

	@property
	def world_opacity(self) -> float:
		return self._world_opacity

	@world_opacity.setter
	def world_opacity(self, new_opac: float) -> None:
		self._world_opacity = new_opac
		self.update_camera()

	@property
	def world_scale(self) -> float:
		return self._world_scale

	@world_scale.setter
	def world_scale(self, new_scale: float) -> None:
		self._world_scale = new_scale
		self.update_camera()

	@property
	def world_scale_x(self) -> float:
		return self._world_scale_x

	@world_scale_x.setter
	def world_scale_x(self, new_scale_x: float) -> None:
		self._world_scale_x = new_scale_x
		self.update_camera()

	@property
	def world_scale_y(self) -> float:
		return self._world_scale_y

	@world_scale_y.setter
	def world_scale_y(self, new_scale_y: float) -> None:
		self._world_scale_y = new_scale_y
		self.update_camera()
