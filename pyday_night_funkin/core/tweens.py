
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
