
import typing as t

if t.TYPE_CHECKING:
	from pyglet.graphics import Batch, Group


class Context():
	"""
	Graphics context, which is effectively fancy talk for a pyglet
	batch and group.
	"""

	__slots__ = ("batch", "group")

	def __init__(self, batch: "Batch", group: "Group") -> None:
		self.batch = batch
		self.group = group
