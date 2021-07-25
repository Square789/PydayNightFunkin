
def clamp(value, min_, max_):
	return min_ if value < min_ else (max_ if value > max_ else value)
