
from math import sin, pi, tau

eta = pi * 0.5


# https://easings.net cool site

def linear(x: float) -> float:
	return x

def in_cubic(x: float) -> float:
	return x**3

def out_cubic(x: float) -> float:
	return 1 - (1 - x)**3

def in_out_cubic(x: float) -> float:
	return 4 * x**3 if x < 0.5 else 1 - ((-2*x + 2)**3 / 2)

def in_quart(x: float) -> float:
	return x**4

def out_quart(x: float) -> float:
	return 1 - (1 - x)**4

def in_out_quart(x: float) -> float:
	return 8 * x**4 if x < 0.5 else 1 - ((-2*x + 2)**4 / 2)

def in_quad(x: float) -> float:
	return x**2

def out_quad(x: float) -> float:
	return 1 - (1 - x)**2

def in_out_quad(x: float) -> float:
	return 2 * x**2 if x < 0.5 else 1 - ((-2*x + 2)**2 / 2)

def in_elastic(x: float) -> float:
	return -(
		(2.0**(10.0 * (x - 1.0))) *
		sin(((x - 1.0) - (0.4 / tau * eta)) * (tau / 0.4))
	)
	# -(
	# 	AMPL *
	# 	(2.0**(10.0 * (x - 1.0))) *
	# 	sin(((x - 1.0) - (PER / tau * asin(1.0 / AMPL))) * tau / PER)
	# )

def out_elastic(x: float) -> float:
	return (
		(2.0**(-10.0 * x)) * sin((x - (0.4 / tau * eta)) * tau / 0.4) + 1.0
	)
	# (AMPL * pow(2, -10 * t) * sin((t - (PER / (2 * PI) * asin(1 / AMPL))) * (2 * PI) / PER) + 1)

def in_out_elastic(x: float) -> float:
	if (x < 0.5):
		res = -0.5 * ((2.0**(10.0*(x - 0.5))) * sin(((x - 0.5) - 0.1) * tau / 0.4))
	else:
		res = 0.5 * (2.0**(-10.0*(x - 0.5))) * sin((x - 0.5) - 0.1 * tau / 0.4) + 1.0

	return res
