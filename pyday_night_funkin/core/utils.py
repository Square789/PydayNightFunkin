
from itertools import islice
import typing as t

from pyday_night_funkin.core.constants import ADDRESS_PADDING

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite

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

def dump_id(x: object) -> str:
	return f"0x{id(x):0>{ADDRESS_PADDING}}"

def dump_sprite_info(s: "PNFSprite") -> None:
	print(f"Offset: {s.offset}")
	print(f"Origin: {s.origin}")
	print(f"Frame offset: {s._frame.offset}")
	print(f"Frame source size: {s._frame.source_dimensions}")
	print(f"w, h: {s._width}, {s._height}")
	print()
