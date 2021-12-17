
from collections import defaultdict
import ctypes
import typing as t

from loguru import logger
from pyglet.gl import gl
from pyglet.graphics import vertexbuffer

from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain, PNFVertexList
from pyday_night_funkin.core.graphics.shared import C_TYPE_MAP, GL_TYPE_SIZES, RE_VERTEX_FORMAT
from pyday_night_funkin.core.graphics import states

if t.TYPE_CHECKING:
	from .pnf_group import PNFGroup


_INDEX_TYPE = gl.GL_UNSIGNED_INT
_INDEX_TYPE_SIZE = GL_TYPE_SIZES[_INDEX_TYPE]


class _AnnotatedGroup:
	"""
	Tiny dataclass to store a group along with its vertex list.
	To be used only during draw list creation.
	"""
	__slots__ = ("group", "vertex_list")

	def __init__(self, group: "PNFGroup", data: "GroupData") -> None:
		self.group = group
		self.vertex_list = data.vertex_list


# NOTE: This is just a class with a list. May be useful for further
# work, may also turn out completely useless.
class GroupChain:
	def __init__(self, groups: t.Sequence["_AnnotatedGroup"]) -> None:
		self.groups = groups
		# self.used_vertex_domains = {g.vertex_list.domain for g in groups}
		# self.used_draw_modes = {g.vertex_list.draw_mode for g in groups}

	def _dump(self) -> str:
		r = f"<{self.__class__.__name__}\n"
		for c in self.groups:
			r += "  " + repr(c) + "\n"
		r += ">"
		return r


class GroupData:
	__slots__ = ("vertex_list", "children")

	def __init__(
		self,
		vertex_list: t.Optional["PNFVertexList"] = None,
		children: t.Iterable["PNFGroup"] = (),
	) -> None:
		self.vertex_list = vertex_list
		self.children = list(children)


class PNFBatch:
	"""
	Poor attempt at turning pyglet's drawing system upside down.
	This batch only works in conjunction with PNFGroups and tries
	to minimize the amount of OpenGL calls made during a draw cycle
	while facing many sprites of a different order.
	"""

	def __init__(self) -> None:
		self._top_groups: t.List["PNFGroup"] = []
		self._group_data: t.Dict["PNFGroup", "GroupData"] = defaultdict(GroupData)

		self._draw_list_dirty = True
		self._draw_list = []
		"""List of functions to call in-order to draw everything that
		needs to be drawn."""

		self._vertex_domains: t.Dict[t.Tuple[str, ...], "PNFVertexDomain"] = {}
		self._index_buffer = None

	def _add_group(self, group: "PNFGroup") -> None:
		if group.parent is None:
			self._top_groups.append(group)
		else:
			if group.parent not in self._group_data:
				self._add_group(group.parent)
			self._group_data[group.parent].children.append(group)

		self._draw_list_dirty = True

	def _get_vertex_domain(self, attr_bundle: t.Sequence[str]) -> PNFVertexDomain:
		"""
		Get an existing or newly created vertexdomain for the given
		vertex attribute bundle.
		"""
		attr_bundle = tuple(attr_bundle)
		if attr_bundle not in self._vertex_domains:
			self._vertex_domains[attr_bundle] = PNFVertexDomain(attr_bundle)

		return self._vertex_domains[attr_bundle]

	def _set_index_buffer(self, data: t.Sequence[int]) -> None:
		"""
		Sets the content of the index buffer to the given data and
		refreshes all VAOs of all vertex domains to use it.
		"""
		indices = (C_TYPE_MAP[_INDEX_TYPE] * len(data))(*data)
		if self._index_buffer is not None:
			self._index_buffer.delete()

		self._index_buffer = vertexbuffer.create_buffer(
			GL_TYPE_SIZES[_INDEX_TYPE] * len(indices),
			gl.GL_ELEMENT_ARRAY_BUFFER,
			gl.GL_STATIC_DRAW,
		)
		self._index_buffer.set_data(indices)
		for dom in self._vertex_domains.values():
			for vao in dom._vaos.values():
				gl.glBindVertexArray(vao)
				gl.glBindBuffer(self._index_buffer.target, self._index_buffer.id)
				gl.glBindVertexArray(0)

	def _group_drawability_check(self, group: "PNFGroup") -> bool:
		"""
		Checks whether a group's vertex list has been deleted.
		If it was, removes it from the group's group data.
		Returns whether a group has a vertex list and is visible.
		"""
		gd = self._group_data[group]
		if gd.vertex_list is None:
			return False

		if gd.vertex_list.deleted:
			gd.vertex_list = None
			return False

		return group.visible

	def visit(self, group: "PNFGroup") -> t.List[t.List["PNFGroup"]]:
		"""
		Visits groups recursively.
		Returns a list of lists of Groups where all of the inner list's
		order between groups is irrelevant, but the order of outer
		lists must be kept.
		"""
		chains = []
		if self._group_drawability_check(group):
			chains.append([group])

		if self._group_data[group].children:
			# The only case where order can be dropped is if many childless
			# groups of same order are on the same level.
			sc = sorted(self._group_data[group].children)
			cur_order = sc[0].order
			cur_group_list: t.List["PNFGroup"] = []
			for child_group in sc:
				if child_group.order != cur_order:
					chains.append(cur_group_list)
					cur_group_list = []
					cur_order = child_group.order

				for subchain in self.visit(child_group):
					cur_group_list.extend(subchain)

			if cur_group_list:
				chains.append(cur_group_list)

		return chains

	def _create_draw_list(self) -> t.Tuple[t.List[t.Callable[[], t.Any]], t.List[int]]:
		"""
		Builds a draw list and an index array from the given top groups
		and group data.
		"""
		chains: t.List[GroupChain] = []
		for group in sorted(self._top_groups):
			chains.extend(
				GroupChain(_AnnotatedGroup(g, self._group_data[g]) for g in raw_chain)
				for raw_chain in self.visit(group)
			)

		# Below converts the group chains into GL calls.
		# TODO: This can certainly be optimized further by reordering
		# groups that share a GroupChain.
		# Unfortunately, I am too stupid to figure out how.

		if not chains:
			return [], []

		state_wall = states.PseudoStateWall()
		draw_list = []
		indices = []
		# Vertex layout is dictated by vertex domain and a group's program.
		cur_vertex_layout = None
		cur_draw_mode = None
		cur_index_start = 0
		cur_index_run = 0

		for chain in chains:
			for agroup in chain.groups:
				# Extend the draw list with necessary state switch calls
				state_switches = state_wall.switch(agroup.group.states)

				n_vertex_layout = (agroup.vertex_list.domain, agroup.group.program.id)
				n_draw_mode = agroup.vertex_list.draw_mode

				# Any of these unfortunately force a new draw call
				if (
					state_switches or
					n_draw_mode != cur_draw_mode or
					cur_vertex_layout != n_vertex_layout
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

					if cur_vertex_layout != n_vertex_layout:
						def bind_vao(d=agroup.vertex_list.domain, p=agroup.group.program):
							# TODO: Buffers store their data locally and need to be bound
							# to upload it.
							# This binding would always occurr in pyglet's default renderer
							# since it does not utilize VAOs, but needs to be
							# done explicitly here.
							# Maybe there's something that would be able to
							# get rid of these bind calls. (glMapNamedBufferRange?)
							for att in d.attributes.values():
								att.gl_buffer.bind()
							d.bind_vao(p)

						draw_list.append(bind_vao)
						cur_vertex_layout = n_vertex_layout

					cur_draw_mode = n_draw_mode
					draw_list.extend(state_switches)

				# Extend vertex indices
				indices.extend(agroup.vertex_list.indices)
				cur_index_run += len(agroup.vertex_list.indices)

		# Final draw call
		def final_draw_elements(
			m=cur_draw_mode, c=cur_index_run, t=_INDEX_TYPE,
			s=cur_index_start*_INDEX_TYPE_SIZE, v=cur_vertex_layout[0]
		):
			gl.glDrawElements(m, c, t, s)
			v.unbind_vao()

		draw_list.append(final_draw_elements)

		return draw_list, indices

	def _regenerate_draw_list(self) -> None:
		dl, indices = self._create_draw_list()
		self._set_index_buffer(indices)
		self._draw_list = dl
		self._draw_list_dirty = False

	def add(self, size, draw_mode, group, *data) -> PNFVertexList:
		# NOTE: This is somewhat iffy, but on the other hand allowing non-
		# indexed vertex lists would mean even more frequent switches between
		# draw calls.
		# Plus, in this project, most drawables are indexed sprites anyways.
		return self.add_indexed(self, size, draw_mode, group, [*range(size)], *data)

	def add_indexed(self, size, draw_mode, group, indices, *data) -> PNFVertexList:
		attr_names = [x[0] if isinstance(x, tuple) else x for x in data]
		self._add_group(group)

		vtx_list = self._get_vertex_domain(attr_names).create_vertex_list(
			size, group, draw_mode, indices
		)
		self._group_data[group].vertex_list = vtx_list

		# Set initial data
		for x in data:
			if not isinstance(x, tuple):
				continue
			name = RE_VERTEX_FORMAT.match(x[0])[1]
			getattr(vtx_list, name)[:] = x[1]

		self._draw_list_dirty = True

		return vtx_list

	def draw(self):
		if self._draw_list_dirty:
			self._regenerate_draw_list()

		self._index_buffer.bind()
		for f in self._draw_list:
			f()

	def draw_subset(self) -> None:
		raise NotImplementedError("This function was unused anyways")

	def migrate(self, *args, **kwargs) -> None:
		raise NotImplementedError("shut up pls")

	def _dump_draw_list(self) -> None:
		print(self._dump())

	def _dump(self) -> str:
		r = ""
		for k, v in self._vertex_domains.items():
			r += repr(k) + ": " + repr(v) + "\n"
			for name, attr in v.attributes.items():
				r += f"  {name:<20}: {attr!r}\n"
				arr_ptr = ctypes.cast(attr.gl_buffer.data, ctypes.POINTER(attr.c_type))
				r += (" " * 22) + ": "
				r += ' '.join(
					str(arr_ptr[x])
					for x in range(min(100, attr.gl_buffer.size // ctypes.sizeof(attr.c_type)))
				)
				r += "\n"
			r += "\n"

		idx_type = C_TYPE_MAP[_INDEX_TYPE]
		idx_ptr = ctypes.cast(self._index_buffer.data, ctypes.POINTER(idx_type))
		r += "\nIndex buffer: "
		r += ' '.join(
			str(idx_ptr[x])
			for x in range(min(100, self._index_buffer.size // ctypes.sizeof(idx_type)))
		)

		return r
