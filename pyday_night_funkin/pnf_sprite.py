
import typing as t

from pyglet.sprite import Sprite
from pyglet.gl import GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA

class OffsetAnimationFrame():
	"""
	Similar to pyglet's AnimationFrame, except it stores a per-frame
	offset that should be applied to its receiving sprite's x and y
	coordinates.
	"""

	__slots__ = ("image", "duration", "coord_offset")

	def __init__(self, image, duration, coord_offset = None) -> None:
		self.image = image
		self.duration = duration
		self.coord_offset = coord_offset if coord_offset is not None else (0, 0)

	def __repr__(self):
		return (
			f"AnimationFrame({self.image}, duration={self.duration}, "
			f"coord_offset={self.coord_offset})"
		)

class PNFSprite(Sprite):
	"""
	WARNING: This subclass meddles with many underscore-prepended
	attributes of the standard pyglet Sprite, which may completely
	break it in any other pyglet releases.
	"""
	def __init__(
		self,
		img, x = 0, y = 0,
		blend_src = GL_SRC_ALPHA,
		blend_dest = GL_ONE_MINUS_SRC_ALPHA,
		batch = None,
		group = None,
		usage = "dynamic",
		subpixel = False,
		# program = None,
	) -> None:
		super().__init__(img, x, y, blend_src, blend_dest, batch, group, usage, subpixel)
		self._animations = {}

	def add_animation(self, name: str, frames: t.Sequence[OffsetAnimationFrame]):
		self._animations[name] = frames
