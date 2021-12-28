
import typing as t

from pyday_night_funkin.core.graphics.states import ProgramStateMutator

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.states import AbstractStateMutator


class PNFGroup:
	def __init__(
		self,
		parent: t.Optional["PNFGroup"] = None,
		order: int = 0,
		states: t.Sequence["AbstractStateMutator"] = (),
	) -> None:
		"""
		Groups supply an OpenGL state via their state mutators and
		Define an ordered tree which dictated element draw order.
		! WARNING ! Groups are supposed to be immutable, it is best
		to recreate them whenever they should be modified.
		"""
		self.parent = parent
		self.order = order
		self.states = {}
		for state in states:
			if (type_ := type(state)) in self.states:
				raise ValueError(
					"Can't have duplicate states! "
					"I may get around to creating something for that or I may not."
				)
			self.states[type_] = state

		if not ProgramStateMutator in self.states:
			# raise ValueError("Each group requires a `ProgramStateMutator`!")
			# Errors way later when a draw list is built with this group
			self.program = None
		else:
			self.program = self.states[ProgramStateMutator].program

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
