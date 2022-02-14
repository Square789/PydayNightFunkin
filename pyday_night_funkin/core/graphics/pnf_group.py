
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.state import GLState


class PNFGroup:
	"""
	Groups supply an OpenGL state and define an ordered tree which
	dictates element draw order.
	! WARNING ! Groups are mutable, but any changes to them must
	immediatedly be reported to associated interfacers.
	TODO this sucks, find workarounds.
	"""

	def __init__(
		self,
		parent: t.Optional["PNFGroup"] = None,
		order: int = 0,
		state: t.Optional["GLState"] = None,
	) -> None:
		self.parent = parent
		self.order = order
		self.state = state
		self.visible = True

		# if state is None or self.state.program is None:
		# 	# Errors way later when a draw list is built with this group
		# 	# raise ValueError("Each group requires a `ProgramStatePart`!")
		# 	self.program = None
		# else:
		# 	self.program = self.state.program

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
			f"<{self.__class__.__name__} order={self.order} at 0x{id(self):>016X}>"
		)
