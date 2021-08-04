# https://easings.net cool site

from enum import Enum


def linear(x: float) -> float:
	return x

def in_cubic(x: float) -> float:
	return x**3

def out_cubic(x: float) -> float:
	return 1 - (1 - x)**3

def in_out_cubic(x: float) -> float:
	return 4 * x**3 if x < 0.5 else 1 - ((-2*x + 2)**3 / 2)
