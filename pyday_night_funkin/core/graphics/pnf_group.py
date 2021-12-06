
import typing as t

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram


class PNFGroup:
	def __init__(
		self,
		program: "ShaderProgram",
		parent: t.Optional["PNFGroup"],
		order: int = 0,
	) -> None:
		self.program = program
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
			f"<{self.__class__.__name__} order={self.order} at 0x{id(self):>016X}>"
		)
