
from itertools import islice
import sys
import typing as t

import pyglet
from pyglet.image import CheckerImagePattern, ImageData, Texture


if t.TYPE_CHECKING:
	from pyday_night_funkin.core.types import Numeric

T = t.TypeVar("T")
U = t.TypeVar("U")
V = t.TypeVar("V")


ADDRESS_PADDING = (sys.maxsize.bit_length() + 1) // 4
ADDRESS_FSTR = f"0x{{:0>{ADDRESS_PADDING}x}}"


def get_error_tex() -> Texture:
	"""
	Retrieves the global error texture, creating it if it does not
	exist.
	"""
	space = pyglet.gl.current_context.object_space
	try:
		return space.pnf_error_tex
	except AttributeError:
		space.pnf_error_tex = CheckerImagePattern(
			(0xFF, 0x00, 0xFF, 0xFF),
			(0x00, 0x00, 0x00, 0xFF),
		).create_image(16, 16).create_texture(Texture)
	return space.pnf_error_tex

def get_pixel_tex() -> Texture:
	"""
	Retrieves the global pixel texture, creating it if it does not
	exist.
	"""
	space = pyglet.gl.current_context.object_space
	try:
		return space.pnf_pixel_tex
	except AttributeError:
		space.pnf_pixel_tex = ImageData(1, 1, "RGBA", b"\xFF\xFF\xFF\xFF").get_texture()
	return space.pnf_pixel_tex


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

	def __len__(self) -> int:
		return min(0, self.end - self.start)

	def __getitem__(self, idx: int) -> T:
		l = len(self)
		if idx < 0:
			idx += l
		if idx < 0 or idx >= l:
			raise IndexError("ListWindow index out of range")
		return self.list[self.start + idx]


def clamp(value: T, min_: U, max_: V) -> t.Union[T, U, V]:
	return min_ if value < min_ else (max_ if value > max_ else value)

def lerp(start: "Numeric", stop: "Numeric", ratio: "Numeric") -> "Numeric":
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

def to_rgb_tuple(v: int) -> t.Tuple[int, int, int]:
	"""
	Converts an RGBA color int to an RGB tuple as pyglet expects it in
	some other places.
	"""
	return tuple(i & 0xFF for i in (v >> 24, v >> 16, v >> 8))

def dump_id(x: object) -> str:
	return ADDRESS_FSTR.format(id(x))

class _Has_next(t.Protocol[T]):
	_next: t.Optional[T]

_Has_nextT = t.TypeVar("_Has_nextT", bound="_Has_next")

def linked_list_iter(head: t.Optional[_Has_nextT]) -> t.Iterator[_Has_nextT]:
	c = head
	while c is not None:
		yield c
		c = c._next
