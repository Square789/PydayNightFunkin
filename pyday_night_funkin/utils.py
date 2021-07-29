
import typing as t


def clamp(value, min_, max_):
	return min_ if value < min_ else (max_ if value > max_ else value)

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
