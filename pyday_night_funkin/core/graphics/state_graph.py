
# This is unfinished (pretty obvious), likely unnecessary and may
# never be implemented.

class StateGraph:
	"""
	A graph that maintains an optimal path through all its nodes and allows
	node access via a dict.
	"""

	def __init__(self) -> None:
		self._s = {}

