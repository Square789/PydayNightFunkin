
from enum import IntEnum

class TWEEN(IntEnum):
	LINEAR = 0
	IN_CUBIC = 1
	OUT_CUBIC = 2
	IN_OUT_CUBIC = 3


# https://easings.net cool site

def linear(x):
	return x

def in_cubic(x):
	return x**3

def out_cubic(x):
	return 1 - (1 - x)**3

def in_out_cubic(x):
	return 4 * x**3 if x < 0.5 else 1 - ((-2*x + 2)**3 / 2)

TWEENS = {
	TWEEN.LINEAR: linear,
	TWEEN.IN_CUBIC: in_cubic,
	TWEEN.OUT_CUBIC: out_cubic,
	TWEEN.IN_OUT_CUBIC: in_out_cubic,
}
