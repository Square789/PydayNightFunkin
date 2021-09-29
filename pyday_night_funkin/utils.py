
from itertools import islice
import typing as t


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


class CtxGuard():
	def __init__(self):
		self._active = False

	def __bool__(self):
		return self._active

	def __enter__(self):
		self._active = True

	def __exit__(self, *_):
		self._active = False


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

