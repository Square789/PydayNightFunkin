
from enum import IntEnum


class TWEEN_ATTR(IntEnum):
	X = 0
	Y = 1
	ROTATION = 2
	OPACITY = 3
	SCALE = 4
	SCALE_X = 5
	SCALE_Y = 6


# https://easings.net cool site

def linear(x: float) -> float:
	return x

def in_cubic(x: float) -> float:
	return x**3

def out_cubic(x: float) -> float:
	return 1 - (1 - x)**3

def in_out_cubic(x: float) -> float:
	return 4 * x**3 if x < 0.5 else 1 - ((-2*x + 2)**3 / 2)
