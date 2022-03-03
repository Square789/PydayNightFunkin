
import typing as t


if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.state import GLState
	from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain
	from pyday_night_funkin.core.graphics.pnf_batch import PNFBatch


# Because it enters your face! GET IT? IT ENTERS YOUR FACE!

class PNFBatchInterfacer:
	"""
	Yet more intellectual property theft from pyglet, this interfacer
	incorporates a pyglet vertex list, which tracks a position in a
	vertex buffer its vertices belong to and is passed to higher
	drawables for management of those.
	It is also used to notify the batch of partial state updates.
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

		self._visible: bool = True
		# TODO move the `visible` setter from the group in here and
		# make groups static again
		# MGSA 2022

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
			new_attr.set_raw_data(
				new_start,
				self.size,
				cur_attr.get_data(self.domain_position, self.size),
			)

		self.domain.deallocate(self.domain_position, self.size)
		self.domain = new_domain
		self.domain_position = new_start
		self.indices = tuple(i + index_shift for i in self.indices)
		self.batch = new_batch

	def set_states(self, new_states: t.Dict[t.Hashable, "GLState"]) -> None:
		# HACK aaaaaa make functions for this
		for dl_id, state in new_states.items():
			dl = self.batch._draw_lists[dl_id]
			dl._group_data[dl._interfacers[self]].state = state
			dl._dirty = True

	def set_visibility(self, new_visibility: bool) -> None:
		if self._visible == new_visibility:
			return

		for dl_id in self.batch._interfacers[self]:
			# _visible is read from the interfacer, this should do it
			self.batch._draw_lists[dl_id]._dirty = True

		self._visible = new_visibility

	def set_data(self, name: str, value: t.Any) -> None:
		"""
		Sets vertex data of this interfacer for the given attribute.
		"""
		self.domain.attributes[name].set_data(self.domain_position, self.size, value)
