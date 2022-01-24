
import typing as t

if t.TYPE_CHECKING:
	import ctypes
	from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain
	from pyday_night_funkin.core.graphics.pnf_batch import PNFBatch


class PNFBatchInterfacer:
	"""
	Yet more intellectual property theft from pyglet, this interfacer
	incorporates a pyglet vertex list, which tracks a position in a
	vertex buffer its vertices belong to and is passed to higher
	drawables for management of those.
	However, it is also used to notify the batch of partial state
	updates.
	! WARNING ! Forgetting to call `delete` on this will leak
	memory in the list's domain.
	"""

	def __init__(
		self,
		vertex_domain: "PNFVertexDomain",
		domain_position: int,
		size: int,
		draw_mode: int,
		indices: t.Sequence[int],
		batch: "PNFBatch",
	) -> None:
		self.domain = vertex_domain

		self.domain_position = domain_position
		"""
		Position inside the vertex domain. Consider:
		```
		pos2f   . . . .-. . . .|X X X X.X X X X|X X X X.X X ...
		color3B .-.-.|X.X.X|X.X.X|.-.-.|.-.-.|.-.-.|.-.-.|. ...
		```
		An interfacer of `domain_position` 1 and `size` 2 would
		span the region whose bytes are denoted with `X`.
		"""

		self.size = size
		"""
		Amount of vertices in the interfacer.
		"""

		self.draw_mode = draw_mode
		self.indices = tuple(domain_position + i for i in indices)
		"""
		Indices the interfacer's vertices should be drawn with.
		These are absolute to the vertex domain's buffers, so taking
		the example from `domain_position`'s docstring, [1, 2, 1] would
		be valid and [0, 1, 3] would not.
		"""

		self.deleted = False
		"""
		Whether this interfacer has been deleted and is effectively
		junk. Modify this and suffer the consequences; Use `delete()`
		to delete it properly!
		"""

		self.batch = batch

	def delete(self):
		"""
		Deletes this interfacer.
		Tells the vertex domain this interfacer belongs to to
		free the space occupied and notifies its batch of its removal.
		After deletion, it should not be used anymore.
		"""
		if self.deleted:
			return

		self.domain.deallocate(self.domain_position, self.size)
		self.batch._remove_interfacer(self)
		self.batch = None # Friendship ended
		self.deleted = True

	def migrate(self, new_batch: "PNFBatch", new_domain: "PNFVertexDomain") -> None:
		"""
		Migrates the interfacer into a new batch and a new domain,
		deallocating its used space in the old one and occupying new
		space in the, well, new one.
		"""
		if self.domain.attributes.keys() != new_domain.attributes.keys():
			raise ValueError("Vertex domain attribute bundle mismatch!")

		new_start = new_domain.allocate(self.size)
		index_shift = -self.domain_position + new_start
		for k, cur_attr in self.domain.attributes.items():
			new_attr = new_domain.attributes[k]
			new_attr.get_region(new_start, self.size).array[:] = \
				cur_attr.get_region(self.domain_position, self.size).array[:]

		self.domain.deallocate(self.domain_position, self.size)
		self.domain = new_domain
		self.domain_position = new_start
		self.indices = tuple(i + index_shift for i in self.indices)
		self.batch = new_batch

	# TODO get rid of the BufferRegion abstractions.
	# Yes, they are nice, but I am not using interleaved buffers, so all they
	# are is an additional heap allocation that interferes with my optimization trip.
	def set_data(self, name: str, value: t.Any) -> None:
		"""
		Sets data of this interfacer for the given attribute.
		"""
		self.get_data(name)[:] = value

	def get_data(self, name: str) -> "ctypes.Array":
		"""
		Returns a modifiable view of the given attribute's buffer
		region this interfacer owns.
		"""
		reg = self.domain.attributes[name].get_region(self.domain_position, self.size)
		reg.invalidate()
		return reg.array
