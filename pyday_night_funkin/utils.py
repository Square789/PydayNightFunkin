
from itertools import islice
import typing as t

from pyglet.image import ImageData

if t.TYPE_CHECKING:
	from pyglet.image import Texture


T = t.TypeVar("T")


class ListWindow(t.Generic[T]):
	def __init__(
		self,
		list_: t.List[T],
		start: t.Optional[int] = None,
		end: t.Optional[int] = None,
	) -> None:
		self.list = list_
		self.start = start if start is not None else 0
		self.end = end if end is not None else len(list_)

	def __iter__(self) -> t.Iterator[T]:
		return islice(self.list, self.start, self.end)


class FrameInfoTexture():
	"""
	Composite class to store the special per-frame offsets found in
	the xml files alongside a Texture (or TextureRegion).
	"""
	def __init__(
		self,
		texture: "Texture",
		has_frame_info: bool,
		frame_info: t.Optional[t.Tuple[int, int, int, int]] = None,
	) -> None:
		self.texture = texture
		self.has_frame_info = has_frame_info
		self.frame_info = frame_info \
			if has_frame_info and frame_info is not None \
			else (0, 0, texture.width, texture.height)


def clamp(value, min_, max_):
	return min_ if value < min_ else (max_ if value > max_ else value)

def lerp(start, stop, ratio):
	return start + (stop - start) * ratio

def to_rgba_bytes(v: int) -> bytes:
	"""
	Converts an RGBA color int to raw bytes.
	"""
	return bytes(i & 0xFF for i in (v >> 24, v >> 16, v >> 8, v))

def to_rgba_tuple(v: int) -> t.Tuple[int, int, int, int]:
	"""
	Converts an RGBA color int to a tuple as pyglet expects it.
	"""
	return tuple(i & 0xFF for i in (v >> 24, v >> 16, v >> 8, v))

def to_rgb_tuple(v: int) -> t.Tuple[int, int, int, int]:
	"""
	Converts an RGBA color int to an RGB tuple as pyglet expects it in
	some other places.
	"""
	return tuple(i & 0xFF for i in (v >> 24, v >> 16, v >> 8))
