from timeit import timeit

class A:
	def __init__(self):
		self._x = 0

	def _get_x(self):
		return self._x
	def _set_x(self, nx):
		self._x = nx
	x = property(lambda s: s._get_x(), lambda s, v: s._set_x(v))

class B(A):
	def _get_x(self):
		return self._x + 1


class X:
	def __init__(self):
		self._x = 0

	@property
	def x(self):
		return self._x
	@x.setter
	def x(self, nx):
		self._x = nx

class Y(X):
	@property
	def x(self):
		return self._x + 1
	@x.setter
	def x(self, nx):
		self._x = nx


def main():
	a = A()
	print(f"{a.x=}")
	print(f"Setting a.x to 4")
	a.x = 4
	print(f"{a.x=}")
	print()

	b = B()
	print(f"{b.x=}")
	print(f"Setting b.x to 4")
	b.x = 4
	print(f"{b.x=}")
	print()

	x = X()
	print(f"{x.x=}")
	print(f"Setting x.x to 4")
	x.x = 4
	print(f"{x.x=}")
	print()

	y = Y()
	print(f"{y.x=}")
	print(f"Setting y.x to 4")
	y.x = 4
	print(f"{y.x=}")
	print()



if __name__ == "__main__":
	main()

	print("a.x")
	print(timeit(
		"a.x = a.x",
		"a = A()",
		number=5_000_000,
		globals=globals(),
	))

	print("b.x")
	print(timeit(
		"b.x = b.x",
		"b = B()",
		number=5_000_000,
		globals=globals(),
	))

	print("x.x")
	print(timeit(
		"x.x = x.x",
		"x = X()",
		number=5_000_000,
		globals=globals(),
	))

	print("y.x")
	print(timeit(
		"y.x = y.x",
		"y = Y()",
		number=5_000_000,
		globals=globals(),
	))

# Conclusion: Repeating properties is faster, so I will do just that
# Love me some good premature optimization


