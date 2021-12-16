
from collections import defaultdict
import ctypes
import typing as t

from loguru import logger
from pyglet.gl import gl
from pyglet.graphics import vertexbuffer

from pyday_night_funkin.core.graphics.draw_list_builder import DrawListBuilder
from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain, PNFVertexList
from pyday_night_funkin.core.graphics.shared import C_TYPE_MAP, GL_TYPE_SIZES, RE_VERTEX_FORMAT

if t.TYPE_CHECKING:
	from .pnf_group import PNFGroup


_INDEX_TYPE = gl.GL_UNSIGNED_INT


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
		self._top_groups = []
		self._group_data = defaultdict(GroupData)

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

	def _regenerate_draw_list(self) -> None:
		dl, indices = DrawListBuilder(_INDEX_TYPE).build(self._top_groups, self._group_data)
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
