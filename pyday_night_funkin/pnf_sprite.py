
import typing as t
from pyglet.image import AbstractImage
from pyglet.image.animation import Animation

from pyglet.sprite import Sprite
from pyglet.gl import GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA

import pyday_night_funkin.constants as CNST

if t.TYPE_CHECKING:
	from pyglet.image import Texture
	from pyday_night_funkin.image_loader import FrameInfoTexture


class OffsetAnimationFrame():
	"""
	Similar to pyglet's AnimationFrame, except it also stores a
	per-frame offset that should be applied to its receiving sprite's
	x and y coordinates as well as a name that can be used to identify
	the frame.
	"""

	__slots__ = ("image", "duration", "coord_offset", "name")

	def __init__(self, image, duration, coord_offset, name = "?") -> None:
		self.image = image
		self.duration = duration
		self.coord_offset = coord_offset
		self.name = name

	def __repr__(self):
		return (
			f"AnimationFrame({self.image}, duration={self.duration}, "
			f"coord_offset={self.coord_offset})"
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
	WARNING: This subclass meddles with many underscore-prepended
	attributes of the standard pyglet Sprite, which may completely
	break it in any other pyglet releases.
	"""
	def __init__(
		self,
		image: t.Union[PNFAnimation, AbstractImage] = None,
		x: int = 0,
		y: int = 0,
		# TODO: types below maybe idk
		blend_src = GL_SRC_ALPHA,
		blend_dest = GL_ONE_MINUS_SRC_ALPHA,
		batch = None,
		group = None,
		usage = "dynamic",
		subpixel = False,
		# program = None,
	) -> None:
		if image is None:
			image = CNST.ERROR_TEXTURE

		if isinstance(image, PNFAnimation):
			mh = image.frames[0].image.height
		else:
			mh = image.height

		bly = 720 - y - mh
		super().__init__(image, x, bly, blend_src, blend_dest, batch, group, usage, subpixel)

		self._animations = {}
		self._animation_offset = (0, 0)

	def _animate(self, dt: float) -> None:
		"""
		Disgusting override of underscore method, required to set the
		sprite's position on animation.
		"""
		super()._animate(dt)
		fx, fy = frame_offset = self._animation.frames[self._frame_index].coord_offset[0:2]
		if frame_offset != self._animation_offset:
			cfx, cfy = self._animation_offset
			self.x += cfx
			self.x -= fx
			self.y -= cfy
			self.y += fy
			self._animation_offset = frame_offset

	def _set_texture(self, texture: "Texture") -> None:
		# Overridden to keep the illusion of the sprite growing from the top left.
		prev_h = self._texture.height
		super()._set_texture(texture)
		dif = self._texture.height - prev_h
		self.y -= dif

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

	def play_animation(self, name: str) -> None:
		self.image = self._animations[name]
