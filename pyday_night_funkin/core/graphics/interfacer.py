
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.state import GLState
	from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain
	from pyday_night_funkin.core.graphics.pnf_batch import PNFBatch
	from pyday_night_funkin.core.graphics.pnf_group import PNFGroup


# Because it enters your face! GET IT? IT ENTERS YOUR FACE!

class PNFBatchInterfacer:
	"""
	Yet more intellectual property theft from pyglet, this interfacer
	incorporates a pyglet vertex list, which tracks a position in a
	vertex buffer its vertices belong to and is passed to higher
	drawables for management of those.
	The interfacer's purpose is to make the right calls to the
	graphics backend's trifecta of batches, domains and draw lists,
	all from the viewpoint of a single drawable.

	! WARNING ! Forgetting to call `delete` on this will leak
	memory in the owning vertex domain.
	"""

	# idkfa
	__slots__ = (
		"domain", "domain_position", "size", "draw_mode", "indices", "deleted", "batch",
		"_draw_lists", "_group", "_visible", "__weakref__"
	)

	def __init__(
		self,
		vertex_domain: "PNFVertexDomain",
		domain_position: int,
		size: int,
		draw_mode: int,
		indices: t.Sequence[int],
		batch: "PNFBatch",
		group: "PNFGroup",
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

		self._draw_lists: t.List[t.Hashable] = []

		self._group = group

		self._visible: bool = True

	def delete(self):
		"""
		Deletes this interfacer.
		Tells the vertex domain this interfacer belongs to to
		free the space occupied and notifies its batch of its removal.
		After deletion, it should and can not be used anymore.
		"""
		if self.deleted:
			return

		self.domain.deallocate(self.domain_position, self.size)
		self.batch._remove_interfacer(self)
		del self.batch # Friendship ended
		del self._group
		self.deleted = True

	def change_batch(
		self,
		new_batch: "PNFBatch",
		new_group: t.Optional["PNFGroup"] = None,
		states: t.Optional[t.Dict[t.Hashable, "GLState"]] = None,
	) -> None:
		"""
		Migrates the interfacer into a new batch and a new domain,
		deallocating its used space in the old one and occupying new
		space in the new one.

		A new batch and state dict may also be supplied at the same time.

		If the batch is unchanged, this method does nothing.
		If you want to change only the group or this interfacer's states,
		use ``change_group_and_or_gl_state`` instead.
		"""
		if new_batch is self.batch:
			return

		if new_group is None:
			new_group = self._group

		if states is None:
			states = {x: self.get_state(x) for x in self._draw_lists}

		self.batch._remove_interfacer(self)
		self._migrate_domain(new_batch._get_vertex_domain(self.domain.attribute_bundle))
		self._draw_lists.clear()
		self.batch = new_batch
		self._group = new_group
		self.batch._introduce_interfacer(self, states)

	def _migrate_domain(self, new_domain: "PNFVertexDomain") -> None:
		"""
		Performs all the mutations required to copy vertex data from
		the current domain into a new one.
		"""
		if self.domain.attributes.keys() != new_domain.attributes.keys():
			raise ValueError("Vertex domain attribute bundle mismatch!")

		new_start = new_domain.allocate(self.size)
		index_shift = new_start - self.domain_position
		for k, cur_attr in self.domain.attributes.items():
			new_attr = new_domain.attributes[k]
			new_attr.copy_from_elements(cur_attr, new_start, self.domain_position, self.size)

		self.domain.deallocate(self.domain_position, self.size)
		self.domain = new_domain
		self.domain_position = new_start
		self.indices = tuple(i + index_shift for i in self.indices)

	def change_group_and_or_gl_state(
		self,
		new_group: t.Optional["PNFGroup"] = None,
		new_states: t.Optional[t.Dict[t.Hashable, "GLState"]] = None,
	) -> None:
		"""
		This method is used to change the interfacer's draw states, its
		group within the batch it's currently in, or both at the same time.
		"""
		if new_group is None:
			new_group = self._group

		if new_states is None:
			if new_group != self._group:
				for dl_id in self._draw_lists:
					state = self.get_state(dl_id)
					self.batch.remove_group(dl_id, self._group)
					self.batch.add_group(dl_id, self, new_group, state)
		else:
			pending_dls = set(self._draw_lists)
			for dl_id, state in new_states.items():
				if dl_id in pending_dls:
					# self.batch.modify_group(dl_id, self._group, state)
					self.batch.remove_group(dl_id, self._group)
					pending_dls.remove(dl_id)
				else:
					self.domain.ensure_vao(state.program, self.batch._get_draw_list(dl_id))
				self.batch.add_group(dl_id, self, new_group, state)

			for dl_id in pending_dls:
				self.batch.remove_group(dl_id, self._group)

			self._draw_lists = list(new_states.keys())

		self._group = new_group

	def get_state(self, dl_id: t.Hashable) -> "GLState":
		"""
		Returns the GLState the interfacer's vertices are being drawn
		with in the given draw list.
		The draw list must exist.
		"""
		return self.batch._draw_lists[dl_id]._group_data[self._group].state

	def set_visibility(self, new_visibility: bool) -> None:
		"""
		Sets the visibility of the interfacer's vertices in all of
		their draw lists.
		"""
		if self._visible == new_visibility:
			return

		self._visible = new_visibility

		# TODO this is kinda hackish, but works well enough
		for dl_id in self._draw_lists:
			self.batch._draw_lists[dl_id]._dirty = True

	def set_data(self, name: str, value: t.Collection) -> None:
		"""
		Sets vertex data of this interfacer for the given attribute.
		"""
		self.domain.attributes[name].set_data_py(self.domain_position, self.size, value)
