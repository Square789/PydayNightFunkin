
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup


class Context():
	"""
	Graphics context, which is effectively fancy talk for a pyglet
	batch and group.
	"""

	__slots__ = ("batch", "group")

	def __init__(self, batch: "PNFBatch", group: "PNFGroup") -> None:
		self.batch = batch
		self.group = group
