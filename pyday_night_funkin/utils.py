
from itertools import islice
import typing as t

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

def to_rgba_bytes(v: t.Union[t.Tuple[int, int, int, int], int]) -> bytes:
	if isinstance(v, tuple):
		if len(v) == 4:
			return bytes(v)
		else:
			raise ValueError("Color tuple must be of size 4!")
	elif isinstance(v, int):
		return bytes(i & 0xFF for i in (v >> 24, v >> 16, v >> 8, v))
	else:
		raise TypeError(f"Invalid type for color: {type(v).__name__!r}.")

