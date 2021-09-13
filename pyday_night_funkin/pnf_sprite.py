
from enum import IntEnum
import math
from time import time
import typing as t

import pyglet.clock
from pyglet import gl
import pyglet.graphics
from pyglet.image import AbstractImage, Texture
from pyglet.image.animation import Animation
from pyglet.sprite import Sprite, SpriteGroup

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.utils import clamp

if t.TYPE_CHECKING:
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
	TWEEN_ATTR.X: "x",
	TWEEN_ATTR.Y: "y",
	TWEEN_ATTR.ROTATION: "rotation",
	TWEEN_ATTR.OPACITY: "opacity",
	TWEEN_ATTR.SCALE: "scale",
	TWEEN_ATTR.SCALE_X: "scale_x",
	TWEEN_ATTR.SCALE_Y: "scale_y",
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
		image: Texture,
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
	should be looped and its offset into it.
	It sets the last frame's duration to `None` if it should not be looped.
	"""
	def __init__(
		self,
		frames: t.Sequence[OffsetAnimationFrame],
		offset: t.Optional[t.Tuple[int, int]],
		loop: bool = False,
	):
		super().__init__(frames)

		self.offset = offset
		self.loop = loop

		if not loop:
			self.frames[-1].duration = None


class PNFSpriteGroup(SpriteGroup):
	def __init__(self, sprite: "PNFSprite", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.sprite = sprite

		self._translation_undo = (0.0, 0.0, 0.0)
		self._scale_undo = (1.0, 1.0, 1.0)

	def set_state(self) -> None:
		gl.glEnable(self.texture.target)
		gl.glBindTexture(self.texture.target, self.texture.id)

		gl.glPushAttrib(gl.GL_COLOR_BUFFER_BIT)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(self.blend_src, self.blend_dest)

		gl.glMatrixMode(gl.GL_MODELVIEW)

		sfx, sfy = self.sprite._scroll_factor
		self._translation_undo = (
			-(self.sprite.camera.zoom * sfx * self.sprite.camera.deviance[0] + CNST.GAME_WIDTH / 2),
			-(self.sprite.camera.zoom * sfy * self.sprite.camera.deviance[1] + CNST.GAME_HEIGHT / 2),
			0.0,
		)
		gl.glTranslatef(
			-self._translation_undo[0],
			-self._translation_undo[1],
			0.0,
		)

		if self.sprite.camera.zoom != 0.0:
			self._scale_undo = (1.0/self.sprite.camera.zoom, 1.0/self.sprite.camera.zoom, 1.0)
			gl.glScalef(
				1.0/self._scale_undo[0],
				1.0/self._scale_undo[1],
				1.0,
			)

		gl.glTranslatef(-CNST.GAME_WIDTH / 2, -CNST.GAME_HEIGHT / 2, 0.0)

	def unset_state(self) -> None:
		gl.glMatrixMode(gl.GL_MODELVIEW)
		gl.glTranslatef(CNST.GAME_WIDTH / 2, CNST.GAME_HEIGHT / 2, 0.0)
		gl.glScalef(*self._scale_undo)
		gl.glTranslatef(*self._translation_undo)
		
		gl.glPopAttrib()
		gl.glDisable(self.texture.target)


class PNFSprite(Sprite):
	"""
	TODO doc

	WARNING: This subclass meddles with many underscore-prepended
	attributes of the standard pyglet Sprite, which may completely
	break it in any other pyglet releases.
	"""
	def __init__(
		self,
		camera: "Camera",
		image: t.Optional[t.Union[PNFAnimation, AbstractImage]] = None,
		x: int = 0,
		y: int = 0,
		blend_src = gl.GL_SRC_ALPHA,
		blend_dest = gl.GL_ONE_MINUS_SRC_ALPHA,
		batch = None,
		group = None,
		usage = "dynamic",
		subpixel = False,
	) -> None:
		image = CNST.ERROR_TEXTURE if image is None else image

		self._animations: t.Dict[str, PNFAnimation] = {}
		self._animation_base_box = None
		self._animation_frame_offset = (0, 0)
		self._scroll_factor = (1.0, 1.0)
		self.current_animation: t.Optional[str] = None
		self.camera = camera

		if batch is not None:
			self._batch = batch

		self._x = x
		self._y = y

		self._texture = image.get_texture()

		self._group = PNFSpriteGroup(self, self._texture, blend_src, blend_dest, group)
		self._usage = usage
		self._subpixel = subpixel
		self._create_vertex_list()

	def _apply_post_animate_offset(self) -> bool:
		"""
		"Swaps out" the current animation frame offset with the new
		one. The new one is calculated in this method using the current
		animation frame, the sprite's scale and the animation base box.
		Returns whether a new animation frame offset was applied and
		thus whether the internal world coordinates were modified.
		Does not cause a camera update.
		"""
		cframe = self._animation.frames[self._frame_index]
		nx = round(
			(cframe.frame_info[0] - (self._animation_base_box[0] - cframe.frame_info[2]) // 2) *
			self._scale * self._scale_x
		)
		ny = round(
			(cframe.frame_info[1] - (self._animation_base_box[1] - cframe.frame_info[3]) // 2) *
			self._scale * self._scale_y
		)
		new_frame_offset = (nx, ny)
		if new_frame_offset != self._animation_frame_offset:
			cfx, cfy = self._animation_frame_offset
			self.x += cfx - new_frame_offset[0]
			self.y += cfy - new_frame_offset[1]
			self._animation_frame_offset = new_frame_offset

	def add_animation(
		self,
		name: str,
		anim_data: t.Union[PNFAnimation, t.Sequence["FrameInfoTexture"]],
		fps: float = 24.0,
		loop: bool = False,
		offset: t.Optional[t.Tuple[int, int]] = None,
	) -> None:
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		spf = 1.0 / fps
		if isinstance(anim_data, PNFAnimation):
			self._animations[name] = anim_data
		else:
			frames = [
				OffsetAnimationFrame(tex.texture, spf, tex.frame_info, name)
				for tex in anim_data
			]
			self._animations[name] = PNFAnimation(frames, offset, loop)
		if self._animation_base_box is None:
			self._set_animation_base_box(self._animations[name])

	def _set_animation_base_box(
		self,
		what: t.Union[PNFAnimation, OffsetAnimationFrame, t.Tuple[int, int]],
	) -> None:
		if not isinstance(what, tuple):
			if not isinstance(what, OffsetAnimationFrame):
				if not isinstance(what, PNFAnimation):
					raise TypeError("Invalid type.")
				frame = what.frames[0]
			else:
				frame = what
			new_bb = (frame.frame_info[2] - frame.frame_info[0], frame.frame_info[3] - frame.frame_info[1])
		else:
			new_bb = what
		self._animation_base_box = new_bb

	def play_animation(self, name: str) -> None:
		self.image = self._animations[name]
		self.current_animation = name

	def screen_center(self, screen_dims: t.Tuple[int, int]) -> None:
		"""
		Sets the sprite's world position so that it is centered 
		on screen.
		"""
		self.x = (screen_dims[0] // 2) - self._texture.width * self._scale * self._scale_x
		self.y = (screen_dims[1] // 2) - self._texture.height * self._scale * self._scale_y

	def tween(
		self,
		tween_func: t.Callable[[float], float],
		attributes: t.Dict[TWEEN_ATTR, t.Any],
		duration: float,
		on_complete: t.Callable = None,
		start_delay: float = 0.0,
	) -> None:
		"""
		# TODO write some very cool doc
		"""
		if start_delay < 0.0:
			raise ValueError("Can't start a tween in the past!")
		if start_delay:
			pyglet.clock.schedule_once(
				lambda _: self.tween(tween_func, attributes, duration, on_complete),
				start_delay,
			)
			return

		# 0: initial value; 1: difference
		tween_map = {}
		for attribute, target_value in attributes.items():
			attribute_name = _TWEEN_ATTR_NAME_MAP[attribute]
			initial_value = getattr(self, attribute_name)
			tween_map[attribute_name] = (initial_value, target_value - initial_value)

		start_time = time()
		stop_time = start_time + duration
		time_difference = stop_time - start_time
		cur_time = start_time

		def tween_schedule_func(dt: float):
			nonlocal cur_time
			cur_time += dt
			progress = (clamp(cur_time, start_time, stop_time) - start_time) / time_difference
			for attr_name, (v_ini, v_diff) in tween_map.items():
				setattr(self, attr_name, v_ini + (v_diff * tween_func(progress)))
			if cur_time >= stop_time:
				pyglet.clock.unschedule(tween_schedule_func)
				if on_complete is not None:
					on_complete()

		pyglet.clock.schedule(tween_schedule_func)

	@property
	def scroll_factor(self) -> t.Tuple[float, float]:
		return self._scroll_factor

	@scroll_factor.setter
	def scroll_factor(self, new_sf: t.Tuple[float, float]) -> None:
		self._scroll_factor = new_sf

	@property
	def image(self) -> t.Union[PNFAnimation, AbstractImage]:
		if self._animation is not None:
			return self._animation
		return self._texture

	@image.setter
	def image(self, image: t.Union[PNFAnimation, AbstractImage]) -> None:
		if self._animation is not None:
			pyglet.clock.unschedule(self._animate)
			# Remove the current animation frame's offset (would've been done by self._animate)
			self.x += self._animation_frame_offset[0]
			self.y += self._animation_frame_offset[1]
			self._animation_frame_offset = (0, 0)
			# Remove the animation's general offset
			if self._animation.offset is not None:
				self.x += self._animation.offset[0]
				self.y += self._animation.offset[1]
			self._animation = None
			self.current_animation = None

		if isinstance(image, PNFAnimation):
			self._animation = image
			self._frame_index = 0
			# Apply the animation's general offset
			if self._animation.offset is not None:
				self.x -= self._animation.offset[0]
				self.y -= self._animation.offset[1]
			# Set first frame and apply its offset
			if self._animation.offset is not None:
				self._set_animation_base_box(self._animation)
			self._set_texture(image.frames[0].image.get_texture())
			self._apply_post_animate_offset()
			self._next_dt = image.frames[0].duration
			if len(image.frames) == 1:
				self._next_dt = None
			if self._next_dt is not None:
				pyglet.clock.schedule_once(self._animate, self._next_dt)
		else:
			self._set_texture(image.get_texture())
		self._update_position()

	def _animate(self, dt: float) -> None:
		# Disgusting override of underscore method, required to set the
		# sprite's position on animation.
		super()._animate(dt)
		self._apply_post_animate_offset()

	def _update_position(self):
		# Contains some manipulations to creation to the
		# vertex array since otherwise it would be displayed
		# upside down
		img = self._texture
		scale_x = self._scale * self._scale_x
		scale_y = self._scale * self._scale_y
		if not self._visible:
			vertices = [0, 0, 0, 0, 0, 0, 0, 0]
		elif self._rotation:
			src_y = -img.anchor_y * scale_y

			x1 = -img.anchor_x * scale_x
			y1 = src_y + img.height * scale_y
			x2 = x1 + img.width * scale_x
			y2 = src_y
			x = self._x
			y = self._y
			r = -math.radians(self._rotation)
			cr = math.cos(r)
			sr = math.sin(r)
			ax = x1 * cr - y1 * sr + x
			ay = x1 * sr + y1 * cr + y
			bx = x2 * cr - y1 * sr + x
			by = x2 * sr + y1 * cr + y
			cx = x2 * cr - y2 * sr + x
			cy = x2 * sr + y2 * cr + y
			dx = x1 * cr - y2 * sr + x
			dy = x1 * sr + y2 * cr + y
			vertices = [ax, ay, bx, by, cx, cy, dx, dy]
		elif scale_x != 1.0 or scale_y != 1.0:
			src_y = self._y - (img.anchor_y * scale_y)

			x1 = self._x - img.anchor_x * scale_x
			y1 = src_y + (img.height * scale_y)
			x2 = x1 + img.width * scale_x
			y2 = src_y
			vertices = [x1, y1, x2, y1, x2, y2, x1, y2]
		else:
			src_y = self._y - img.anchor_y

			x1 = self._x - img.anchor_x
			y1 = src_y + img.height
			x2 = x1 + img.width
			y2 = src_y
			vertices = [x1, y1, x2, y1, x2, y2, x1, y2]
		if not self._subpixel:
			vertices = [int(v) for v in vertices]

		self._vertex_list.vertices[:] = vertices

	def _set_texture(self, texture):
		if texture.id is not self._texture.id:
			self._group = PNFSpriteGroup(
				self,
				texture,
				self._group.blend_src,
				self._group.blend_dest,
				self._group.parent
			)
			if self._batch is None:
				self._vertex_list.tex_coords[:] = texture.tex_coords
			else:
				self._vertex_list.delete()
				self._texture = texture
				self._create_vertex_list()
		else:
			self._vertex_list.tex_coords[:] = texture.tex_coords
		self._texture = texture
