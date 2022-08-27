
import typing as t

from pyday_night_funkin.core.utils import dump_id


class PNFGroup:
	"""
	Groups are extremely simple objects that define a tree which
	dictates element draw order.
	"""

	__slots__ = ("parent", "order")

	def __init__(self, parent: t.Optional["PNFGroup"] = None, order: int = 0) -> None:
		self.parent = parent
		self.order = order

	def __gt__(self, other) -> bool:
		if not isinstance(other, PNFGroup):
			return NotImplemented
		return self.order > other.order

	def __lt__(self, other) -> bool:
		if not isinstance(other, PNFGroup):
			return NotImplemented
		return self.order < other.order

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} order={self.order} at {dump_id(self)}>"
		)
