
from collections import defaultdict
import ctypes
import typing as t
from weakref import WeakKeyDictionary

from loguru import logger
from pyglet.gl import gl
from pyglet.graphics import vertexbuffer

from pyday_night_funkin.core.graphics.interfacer import PNFBatchInterfacer
from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain
from pyday_night_funkin.core.graphics.shared import C_TYPE_MAP, GL_TYPE_SIZES, RE_VERTEX_FORMAT
from pyday_night_funkin.core.graphics.state import GLState
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject

if t.TYPE_CHECKING:
	from .pnf_group import PNFGroup


_INDEX_TYPE = gl.GL_UNSIGNED_INT
_INDEX_TYPE_SIZE = GL_TYPE_SIZES[_INDEX_TYPE]


# NOTE: This is just a class with a list. May be useful for further
# work, may also turn out completely useless.
class GroupChain:
	def __init__(self, groups: t.Sequence["GroupData"]) -> None:
		self.groups = list(groups)
		# self.used_vertex_domains = {g.interfacer.domain for g in groups}
		# self.used_draw_modes = {g.interfacer.draw_mode for g in groups}

	def _dump(self) -> str:
		r = f"<{self.__class__.__name__}\n"
		for c in self.groups:
			r += "  " + repr(c) + "\n"
		r += ">"
		return r


class GroupData:
	"""
	GroupData is used to build a group tree by storing an interfacer
	and a group's children, which a group then maps to.
	"""
	__slots__ = ("interfacer", "state", "children")

	def __init__(
		self,
		state: t.Optional[GLState] = None,
		interfacer: t.Optional["PNFBatchInterfacer"] = None,
		children: t.Iterable["PNFGroup"] = (),
	) -> None:
		self.state = state
		self.interfacer = interfacer
		self.children = set(children)


class DrawList:
	"""
	A DrawList encompasses a group tree and hosts functionality to
	create optimized sprite drawing lists using index buffers.
	"""

	def __init__(self) -> None:
		"""
		Initializes a DrawList.
		"""

		self._dirty = True
		self.funcs: t.List[t.Callable[[], t.Any]] = []
		"""
		List of functions to call in-order to draw everything that
		needs to be drawn.
		"""

		self._interfacers: "WeakKeyDictionary[PNFBatchInterfacer, PNFGroup]" = WeakKeyDictionary()
		"""
		Associates each interfacer registered in this draw list owns
		with its group, which is used to get its group data.
		"""

		self._top_groups: t.Set["PNFGroup"] = set()
		self._group_data: t.Dict["PNFGroup", "GroupData"] = defaultdict(GroupData)
		self._index_buffer = None

	# TODO: Useless """optimization""", do it later when the rest works
	# def _add_group_parents(self, group: "PNFGroup") -> None:
	# 	if group in self._group_data:
	# 		return

	# 	if group.parent is None:
	# 		self._top_groups.add(group)
	# 	else:
	# 		if group.parent not in self._group_data:
	# 			self._add_group_parents(group.parent)
	# 		self._group_data[group.parent].children.add(group)

	# 	self._dirty = True

	def add_group(
		self,
		group: "PNFGroup",
		interfacer: PNFBatchInterfacer = None,
		state: t.Optional[GLState] = None,
	) -> None:
		"""
		Add a group and all its parents to the group data
		registry and mark the draw list as dirty.
		If the group is already known, has no effect.
		"""
		if group in self._group_data:
			return

		if group.parent is None:
			self._top_groups.add(group)
		else:
			if group.parent not in self._group_data:
				self.add_group(group.parent)
			self._group_data[group.parent].children.add(group)

		if interfacer is not None:
			self._interfacers[interfacer] = group

		self._group_data[group].interfacer = interfacer
		self._group_data[group].state = state
		self._dirty = True

	def delete_group(self, group: "PNFGroup") -> None:
		"""
		Deletes a group from the group registry and marks the draw
		list as dirty. If a non-leaf node is deleted, it will leave
		a hole in the continuity of the group tree, so don't do that.
		"""
		if group.parent is not None and group.parent in self._group_data:
			self._group_data[group.parent].children.remove(group)
		self._top_groups.discard(group)
		self._group_data.pop(group)

		self._dirty = True

	def remove_interfacer(self, interfacer: PNFBatchInterfacer) -> None:
		"""
		Removes an interfacer from this draw list's group tree.
		"""
		if interfacer not in self._interfacers:
			print("! weird")
			return

		if self._interfacers[interfacer] not in self._group_data:
			print("! mega weird")
			return

		gd = self._group_data[self._interfacers[interfacer]]
		if gd.interfacer is not None:
			gd.interfacer = None
			self._dirty = True
		self._interfacers.pop(interfacer)

	def _visit(self, group: "PNFGroup") -> t.Tuple[t.List[t.List["PNFGroup"]], bool]:
		"""
		Visits groups recursively.
		Returns a tuple of:
		0: A list of lists of Groups where all of the inner list's
		order between groups is irrelevant, but the order of outer
		lists must be kept.
		1: Whether the group visited was considered dangling and has
		been deleted from the group tree.
		"""
		chains = []
		group_intact = self._group_data[group].interfacer is not None
		if group_intact and self._group_data[group].interfacer._visible:
			# Don't draw invisible groups now
			chains.append([group])

		if self._group_data[group].children:
			# The only case where order can be dropped is if many childless
			# groups of same order are on the same level.
			sc = sorted(self._group_data[group].children)
			cur_order = sc[0].order
			cur_group_list: t.List["PNFGroup"] = []

			for child_group in sc:
				# If a child group breaks order (Booo!), add chain so far and reset
				if child_group.order != cur_order:
					if cur_group_list:
						chains.append(cur_group_list)
						cur_group_list = []
					cur_order = child_group.order

				# Extend current chain with all of the child group's subgroups
				subchains, cg_intact = self._visit(child_group)
				# If this group is a connecting group, consider it intact if the
				# children bridge to any drawable child group
				group_intact = group_intact or cg_intact or bool(subchains)
				for subchain in subchains:
					cur_group_list.extend(subchain)

			# Add last outstanding group list
			if cur_group_list:
				chains.append(cur_group_list)

		# This group is dangling, delete it.
		if not group_intact:
			if chains:
				raise RuntimeError(
					"This should not have happened: Group was considered dangling "
					"but delivered chains!"
				)
			self.delete_group(group)

		return chains, group_intact

	def regenerate(self) -> t.Tuple[t.List[t.Callable[[], t.Any]], t.List[int]]:
		"""
		Rebuilds the draw list from the group tree.
		Returns a series of functions that - when called in order -
		will run through all necessary state mutations and draw
		calls to draw the scene which you want to draw and a list
		of indices the index buffer must contain at that point.
		"""
		chains: t.List[GroupChain] = []
		for group in sorted(self._top_groups):
			chains.extend(
				GroupChain(self._group_data[g] for g in raw_chain)
				for raw_chain in self._visit(group)[0]
			)

		# Below converts the group chains into GL calls.
		# TODO: This can certainly be optimized further by reordering
		# groups that share a GroupChain smartly.
		# Unfortunately, I am too stupid to figure out how, so just have
		# a sort by the most expensive thing to switch (shader programs)
		for chain in chains:
			chain.groups.sort(key=lambda g: g.state.program.id)

		if not chains:
			return [], []

		cur_state = GLState.from_state_parts()
		draw_list = []
		indices = []
		# Vertex layout is dictated by vertex domain and a group's program.
		cur_vertex_layout = None
		cur_draw_mode = None
		cur_index_start = 0
		cur_index_run = 0

		for chain in chains:
			for group_data in chain.groups:
				# Get necessary state switch calls
				state_switches = cur_state.switch(group_data.state)
				cur_state = group_data.state

				new_vertex_layout = (group_data.interfacer.domain, group_data.state.program.id)
				new_draw_mode = group_data.interfacer.draw_mode

				# Any of these unfortunately force a new draw call
				if (
					state_switches or
					new_draw_mode != cur_draw_mode or
					cur_vertex_layout != new_vertex_layout
				):
					# Accumulate all indices so far into a draw call (if there were any)
					if cur_index_run > 0:
						def draw_elements(
							m=cur_draw_mode, c=cur_index_run, t=_INDEX_TYPE,
							s=cur_index_start*_INDEX_TYPE_SIZE
						):
							gl.glDrawElements(m, c, t, s)
						draw_list.append(draw_elements)

						cur_index_start += cur_index_run
						cur_index_run = 0

					if cur_vertex_layout != new_vertex_layout:
						def bind_vao(d=group_data.interfacer.domain, p=group_data.state.program):
							# Buffers store their data locally and need to be told to upload it.
							# Using a buffer that does direct glNamedBufferSubData calls noticeably
							# slows down the freeplay scene, where a lot of vertex updates are
							# made each frame.
							for att in d.attributes.values():
								att.gl_buffer.ensure()
							d.bind_vao(p)

						draw_list.append(bind_vao)
						cur_vertex_layout = new_vertex_layout

					# Extend the draw list with the required state switch calls
					cur_draw_mode = new_draw_mode
					draw_list.extend(state_switches)

				# Extend vertex indices
				indices.extend(group_data.interfacer.indices)
				cur_index_run += len(group_data.interfacer.indices)

		# Final draw call
		def final_draw_elements(
			m=cur_draw_mode, c=cur_index_run, t=_INDEX_TYPE,
			s=cur_index_start*_INDEX_TYPE_SIZE, d=cur_vertex_layout[0]
		):
			gl.glDrawElements(m, c, t, s)
			d.unbind_vao()

		draw_list.append(final_draw_elements)

		return draw_list, indices

	def _set_index_buffer(self, data: t.Sequence[int]) -> None:
		"""
		Sets the content of the index buffer to the given data.
		"""
		# and
		# refreshes all VAOs of all vertex domains to use it.
		#"""
		indices = (C_TYPE_MAP[_INDEX_TYPE] * len(data))(*data)
		buf_size = GL_TYPE_SIZES[_INDEX_TYPE] * len(indices)
		if self._index_buffer is None:
			self._index_buffer = BufferObject(
				gl.GL_ELEMENT_ARRAY_BUFFER, buf_size, gl.GL_STATIC_DRAW,
			)
			self._index_buffer.set_data(0, buf_size, indices)
		else:
			self._index_buffer.set_size_and_data(buf_size, indices)

		# for dom in self._vertex_domains.values():
		# 	for vao in dom._vaos.values():
		# 		gl.glBindVertexArray(vao)
		# 		gl.glBindBuffer(self._index_buffer.target, self._index_buffer.id)
		# 		gl.glBindVertexArray(0)

	def draw(self) -> None:
		if self._dirty:
			funcs, indices = self.regenerate()
			self._set_index_buffer(indices)
			self.funcs = funcs
			self._dirty = False

		self._index_buffer.bind()
		for f in self.funcs:
			f()

	def delete(self) -> None:
		"""
		Properly deletes the DrawList and frees up any OpenGL objects.
		"""
		if self._index_buffer is not None:
			self._index_buffer.delete()

		self._group_data = None
		self._top_groups = None


class PNFBatch:
	"""
	Poor attempt at turning pyglet's drawing system upside down.
	This batch is the core part of PydayNightFunkin's rendering
	backend, works in conjunction with PNFGroups and tries
	to minimize the amount of OpenGL calls made during a draw cycle
	while facing many drawables of a strictly different order.
	Unlike pyglet's batch, it is able to construct multiple draw
	lists, aiding in creating a HaxeFlixel-like camera system.
	"""

	def __init__(self) -> None:
		self._draw_lists: t.Dict[t.Hashable, DrawList] = {}
		self._vertex_domains: t.Dict["frozenset[str]", "PNFVertexDomain"] = {}
		self._interfacers: "WeakKeyDictionary[PNFBatchInterfacer, t.Sequence[t.Hashable]]" = \
			WeakKeyDictionary()
		"""
		Associates each interfacer this batch owns with the draw lists
		it exists in.
		"""

	def _get_draw_list(self, name: t.Hashable) -> DrawList:
		"""
		Gets an existing or new draw list.
		"""
		if name not in self._draw_lists:
			self._draw_lists[name] = DrawList()
		return self._draw_lists[name]

	def _get_vertex_domain(self, attr_bundle: t.Iterable[str]) -> PNFVertexDomain:
		"""
		Gets an existing or newly created vertexdomain for the given
		vertex attribute bundle.
		"""
		attr_bundle = frozenset(attr_bundle)
		if attr_bundle not in self._vertex_domains:
			self._vertex_domains[attr_bundle] = PNFVertexDomain(attr_bundle)
		return self._vertex_domains[attr_bundle]

	def add(
		self,
		size: int,
		draw_mode: int,
		group: "PNFGroup",
		states: t.Dict[t.Hashable, GLState],
		*data: t.Union[str, t.Tuple[str, t.Any]],
	) -> PNFBatchInterfacer:
		# NOTE: This is somewhat iffy, but on the other hand allowing non-
		# indexed stuff would mean even more frequent switches between
		# draw calls.
		# In this project, most drawables are indexed sprites anyways.
		return self.add_indexed(size, draw_mode, group, [*range(size)], states, *data)

	def add_indexed(
		self,
		size: int,
		draw_mode: int,
		group: "PNFGroup",
		indices: t.Sequence[int],
		states: t.Dict[t.Hashable, GLState],
		*data: t.Union[str, t.Tuple[str, t.Any]],
	) -> PNFBatchInterfacer:
		attr_names = [x[0] if isinstance(x, tuple) else x for x in data]

		domain = self._get_vertex_domain(attr_names)
		for state in states.values():
			domain.ensure_vao(state.program)

		start = domain.allocate(size)
		interfacer = PNFBatchInterfacer(domain, start, size, draw_mode, indices, self)
		self._introduce_interfacer(interfacer, group, states)

		# Set initial data
		for x in data:
			if not isinstance(x, tuple):
				continue
			name = RE_VERTEX_FORMAT.match(x[0])[1]
			interfacer.set_data(name, x[1])

		return interfacer

	def draw(self, draw_list: t.Hashable):
		self._draw_lists[draw_list].draw()

	def migrate(
		self,
		interfacer: "PNFBatchInterfacer",
		new_group: "PNFGroup",
		new_batch: "PNFBatch",
	) -> None:
		"""
		Migrates the given interfacer so that it is afterwards owned
		by `new_batch` under `new_group`.
		Must be used when a drawable's batch, group or both change.
		"""
		if self != new_batch:
			# Steal interfacer from the group that owns it in this batch
			dl_ids = self._interfacers[interfacer]
			self._remove_interfacer(interfacer)
			new_batch._introduce_interfacer(interfacer, new_group, dl_ids)
		new_domain = new_batch._get_vertex_domain(interfacer.domain.attribute_bundle)
		new_domain.ensure_vao(new_group.state.program)
		interfacer.migrate(new_batch, new_domain)

	def _introduce_interfacer(
		self, if_: "PNFBatchInterfacer", group: "PNFGroup", draw_lists: t.Dict[t.Hashable, GLState]
	) -> None:
		"""
		Introduces an interfacer, the group it was created under and
		the draw lists its vertices should occupy to the batch.
		"""
		for dl_id, state in draw_lists.items():
			dl = self._get_draw_list(dl_id)
			dl.add_group(group, if_, state)

		self._interfacers[if_] = tuple(draw_lists)

	def _remove_interfacer(self, interfacer: "PNFBatchInterfacer") -> None:
		"""
		To be called when an interfacer leaves this batch.
		Removes the interfacer from all draw lists.
		"""
		if interfacer not in self._interfacers:
			return

		for dl_id in self._interfacers[interfacer]:
			self._draw_lists[dl_id].remove_interfacer(interfacer)
		self._interfacers.pop(interfacer)

	def _dump_draw_list(self) -> None:
		pass
	# 	print(self._dump())

	# def _dump(self) -> str:
	# 	r = ""
	# 	for k, v in self._vertex_domains.items():
	# 		r += repr(k) + ": " + repr(v) + "\n"
	# 		for name, attr in v.attributes.items():
	# 			r += f"  {name:<20}: {attr!r}\n"
	# 			arr_ptr = ctypes.cast(attr.gl_buffer.data, ctypes.POINTER(attr.c_type))
	# 			r += (" " * 22) + ": "
	# 			r += ' '.join(
	# 				str(arr_ptr[x])
	# 				for x in range(min(100, attr.gl_buffer.size // ctypes.sizeof(attr.c_type)))
	# 			)
	# 			r += "\n"
	# 		r += "\n"

	# 	idx_type = C_TYPE_MAP[_INDEX_TYPE]
	# 	idx_ptr = ctypes.cast(self._index_buffer.data, ctypes.POINTER(idx_type))
	# 	r += "\nIndex buffer: "
	# 	r += ' '.join(
	# 		str(idx_ptr[x])
	# 		for x in range(min(100, self._index_buffer.size // ctypes.sizeof(idx_type)))
	# 	)

	# 	r += f"\n\Interfacers created and alive: {len(self._interfacers)}"
	# 	r += f"\nGroups in group registry: {len(self._group_data)}"
	# 	r += f"\nCalls in draw list: {len(self._draw_list)}"

	# 	return r


_fake_batch = PNFBatch()
def get_default_batch():
	return _fake_batch
