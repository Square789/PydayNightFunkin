
class PNFGroup:
	def __init__(
		self,
		program,

	) -> None:
		self.program = program



class PNFBatch:
	"""
	Poor attempt at turning pyglet's drawing system upside down.
	This batch only works in conjunction with PNFGroups and tries
	to minimize the amount of OpenGL calls made during a draw cycle.
	"""

	def __init__(self) -> None:
		self._top_groups = []
		self._draw_list = []
		"""
		List of functions to call in-order to draw everything that
		needs to be drawn.
		"""


	def _create_draw_list(self):
		for grp in sorted(self._top_groups):
			pass
