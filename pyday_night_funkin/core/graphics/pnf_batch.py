
from collections import defaultdict
import ctypes
import re
import typing as t

from loguru import logger
from pyglet.gl import gl
from pyglet.graphics import allocation, vertexarray, vertexbuffer

from pyday_night_funkin.core.graphics.draw_list_builder import DrawListBuilder

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram
	from .pnf_group import PNFGroup


INDEX_TYPE = gl.GLuint

class GroupData:
	__slots__ = ("vertex_list", "children")

	def __init__(
		self,
		vertex_list: t.Optional["PNFVertexList"] = None,
		children: t.Iterable["PNFGroup"] = (),
	) -> None:
		self.vertex_list = vertex_list
		self.children = list(children)


# Copypasted from pyglet/graphics/vertexdomain since it's underscore-prefixed
def nearest_pow2(v):
	# From http://graphics.stanford.edu/~seander/bithacks.html#RoundUpPowerOf2
	# Credit: Sean Anderson
	v -= 1
	v |= v >> 1
	v |= v >> 2
	v |= v >> 4
	v |= v >> 8
	v |= v >> 16
	return v + 1


RE_VERTEX_FORMAT = re.compile("(.*)(\d)(.)(n?)/(static|dynamic|stream)")

_TYPE_MAP = {
	'B': gl.GL_UNSIGNED_BYTE,
	'b': gl.GL_BYTE,
	'd': gl.GL_DOUBLE,
	'I': gl.GL_UNSIGNED_INT,
	'i': gl.GL_INT,
	'f': gl.GL_FLOAT,
	'S': gl.GL_UNSIGNED_SHORT,
	's': gl.GL_SHORT,
}

_C_TYPE_MAP = {
	gl.GL_UNSIGNED_BYTE: ctypes.c_ubyte,
	gl.GL_BYTE: ctypes.c_byte,
	gl.GL_DOUBLE: ctypes.c_double,
	gl.GL_UNSIGNED_INT: ctypes.c_uint,
	gl.GL_INT: ctypes.c_int,
	gl.GL_FLOAT: ctypes.c_float,
	gl.GL_UNSIGNED_SHORT: ctypes.c_ushort,
	gl.GL_SHORT: ctypes.c_short,
}

_GL_TYPE_SIZES = {
	gl.GL_UNSIGNED_BYTE: 1,
	gl.GL_BYTE: 1,
	gl.GL_DOUBLE: 8,
	gl.GL_UNSIGNED_INT: 4,
	gl.GL_INT: 4,
	gl.GL_FLOAT: 4,
	gl.GL_UNSIGNED_SHORT: 2,
	gl.GL_SHORT: 2,
}

_USAGE_MAP = {
	"static": gl.GL_STATIC_DRAW,
	"dynamic": gl.GL_DYNAMIC_DRAW,
	"stream": gl.GL_STREAM_DRAW,
}

_INDEX_TYPE = gl.GL_UNSIGNED_BYTE


class PNFVertexList:
	"""
	Yet more intellectual property theft from pyglet, this bootleg
	vertex list tracks a position in a vertex buffer its vertices
	belong to and is passed to higher drawables for management of
	those.
	"""

	def __init__(
		self,
		vertex_domain: "PNFVertexDomain",
		domain_position: int,
		size: int,
		draw_mode: int,
		indices: t.Sequence[int],
	) -> None:
		self.vtxd = vertex_domain

		self.domain_position = domain_position
		"""
		Position inside the vertex domain. Consider:
		```
		pos2f   . . . .-. . . .|X X X X.X X X X|X X X X.X X ...
		color3B .-.-.|X.X.X|X.X.X|.-.-.|.-.-.|.-.-.|.-.-.|. ...
		```
		A vertex list of `domain_position` 1 and `size` 2 would
		span the region whose bytes are denoted with `X`.
		"""

		self.size = size
		"""
		Amount of vertices in the vertex list.
		"""

		self.draw_mode = draw_mode
		self.indices = indices
		"""
		Indices the vertex list's vertices should be drawn with.
		These are absolute to the vertex domain's buffers, so taking
		the example from `domain_position`'s docstring, [1, 2, 1] would
		be valid and [0, 1, 3] would not.
		"""

	def __getattr__(self, name: str) -> t.Any:
		att = self.vtxd.attributes[name]
		byte_size = self.size * att.element_size

		return att.gl_buffer.get_region(
			self.domain_position * att.element_size,
			byte_size,
			ctypes.POINTER(att.c_type * (self.size * att.count)),
		).array

	def __setattr__(self, name: str, value: t.Any) -> None:
		if "domain" in self.__dict__ and name in self.__dict__["domain"].attributes:
			self.__getattr__(name)[:] = value
		else:
			super().__setattr__(name, value)

	def delete(self):
		pass


class PNFVertexDomainAttribute:
	def __init__(
		self,
		binding_point: int,
		count: int,
		type_: int,
		normalize: bool,
		usage: int,
	) -> None:
		self.count = count
		"""Vertex attribute count. One of 1, 2, 3 or 4."""

		self.binding_point = binding_point
		"""
		Binding point the attribute should be bound to. This is NOT the
		shader location!
		"""

		self.type = type_
		self.c_type = _C_TYPE_MAP[type_]
		self.element_size = _GL_TYPE_SIZES[type_] * count
		"""
		Size of a single attribute in bytes, i. e. `2f` -> 8; `3B` -> 3
		"""

		self.buffer_size = self.element_size * PNFVertexDomain.INITIAL_VERTEX_CAPACITY
		"""Size of this attribute's OpenGL buffer, in bytes."""

		self.normalize = normalize
		self.usage = usage

		self.gl_buffer = vertexbuffer.create_buffer(self.buffer_size, usage=usage)

	def set_data_region(self, data: ctypes.Array, start: int, length: int) -> None:
		self.gl_buffer.set_data_region(data, start, length)

	def resize(self, new_capacity: int) -> None:
		"""
		Resizes the attribute's buffer to fit `new_capacity` vertex
		attributes.
		No checks of any kind are made, be sure to pass in an
		acceptable `new_capacity`!
		"""
		self.gl_buffer.resize(new_capacity * self.element_size)
		self.buffer_size = self.gl_buffer.size

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} (OpenGL buffer id {self.gl_buffer.id}) "
			f"count={self.count} type={self.type} normalize={self.normalize} usage={self.usage} "
			f"at 0x{id(self):>016X}>"
		)


class PNFVertexDomain:
	"""
	Somewhat identical to pyglet's VertexDomain, a PNFVertexDomain
	keeps several buffers for bundles of vertex attributes.
	Practically, there should only be a few vertex domains in existence,
	the most prevalent one managing all sprites.

	Vertex domains have a VAO to quickly (?) set up vertex context.
	The vertex attribute bundle is unchangable.
	"""

	INITIAL_VERTEX_CAPACITY = 2048

	def __init__(self, attribute_bundle: t.Sequence[str]) -> None:
		"""
		Creates a new vertex domain.
		`attribute_bundle` should be a sequence of valid vertex attribute
		format strings.
		"""
		# NOTE: This allocator does not track bytes, but only vertices.
		self._allocator = allocation.Allocator(self.INITIAL_VERTEX_CAPACITY)
		self.attributes: t.Dict[str, PNFVertexDomainAttribute] = {}
		self._vaos: t.Dict[int, gl.GLuint] = {}
		self._active_vao: t.Optional[vertexarray.VertexArray] = None

		for i, attr in enumerate(attribute_bundle):
			name, *ctnu = self._parse_attribute(attr)
			self.attributes[name] = PNFVertexDomainAttribute(i, *ctnu)

		self._switch_cost = 7 * len(self.attributes)
		"""
		Cost value to switch to this vertex domain.
		Hardcoded to be 7 per vertex format set per length of attributes.
		Please note that I have no idea if this is a proper value at all.
		"""

	def _parse_attribute(self, attr: str) -> t.Tuple[str, int, int, bool, int]:
		"""
		Parses a pyglet attribute descriptor string (`asdf2f/stream`
		for example), then returns a tuple of its name, count, type,
		normalization and draw usage hint.
		Raises `ValueError` or `KeyError` on failure.
		"""
		if (re_res := RE_VERTEX_FORMAT.match(attr)) is None:
			raise ValueError(f"Invalid attribute format string {attr!r}")
		name, count, type_, norm, usage = re_res.groups()

		count = int(count)
		type_ = _TYPE_MAP[type_]
		normalize = bool(norm)
		usage = _USAGE_MAP[usage]

		if count not in range(1, 5):
			raise ValueError(f"Vertex attribute count must be 1, 2, 3 or 4; was {count}!")

		return (name, count, type_, normalize, usage)

	def ensure_vao(self, shader: "ShaderProgram") -> None:
		"""
		If no VAO for this shader has been created yet,
		sets up all attribute bindings for this vertex domain's managed
		attribute bundle in context of the given shader program
		and stores them in an internal VAO for future use.
		"""
		if shader.id in self._vaos:
			return

		print(f"/// VAO SETUP FOR PROGRAM {shader.id}")
		vao_id = gl.GLuint()
		gl.glCreateVertexArrays(1, vao_id)

		for shader_attr in shader.attributes.values():
			# Attributes are linked with shaders by their name as passed
			# in the vertex list
			if shader_attr.name not in self.attributes:
				raise ValueError(
					f"Shader program {shader.id!r} contained vertex attribute {shader_attr},"
					f"but {self.__class__.__name__} does not know {shader_attr.name!r}."
				)
			attr = self.attributes[shader_attr.name]
			bp = attr.binding_point

			gl.glEnableVertexArrayAttrib(vao_id.value, bp)
			gl.glVertexArrayVertexBuffer(vao_id.value, bp, attr.gl_buffer.id, 0, attr.element_size)
			gl.glVertexArrayAttribBinding(vao_id.value, shader_attr.location, bp)
			gl.glVertexArrayAttribFormat(vao_id.value, bp, attr.count, attr.type, attr.normalize, 0)

		print("/// VAO SETUP DONE")
		# WARNING: Should shaders be deleted and their ids reassigned,
		# this may fail in disgusting ways
		self._vaos[shader.id] = vao_id

	def bind_vao(self, program: "ShaderProgram") -> None:
		"""
		Binds the VAO for the shader program with the given ID.
		Remember to call `unbind_vao` before calling **any** vertex
		gl functions afterwards, otherwise it will be erroneously
		affected.
		Raises `KeyError` if `ensure_vao` was never called for the
		given program.
		"""
		vao = self._vaos[program.id]
		gl.glBindVertexArray(vao.value)
		self._active_vao = vao

	def unbind_vao(self) -> None:
		"""
		Unbinds the active VAO.
		"""
		gl.glBindVertexArray(0)
		self._active_vao = None

	def allocate(self, size: int) -> int:
		"""
		Tries to safely allocate `size` vertices.
		"""
		try:
			return self._allocator.alloc(size)
		except allocation.AllocatorMemoryException:
			new_size = max(nearest_pow2(self._allocator.capacity + 1), nearest_pow2(size))
			self._resize(new_size)
			return self._allocator.alloc(size)

	def _resize(self, new_size: int) -> None:
		# The buffers in `self.attributes` can always hold `self._allocator.capacity`
		# vertices. Resize them if needed.
		self._allocator.set_capacity(new_size)
		for attr in self.attributes.values():
			attr.resize(new_size)

	def create_vertex_list(
		self, vertex_amount: int, group: "PNFGroup", draw_mode: int, indices: t.Sequence[int]
	) -> PNFVertexList:
		self.ensure_vao(group.program)
		start = self.allocate(vertex_amount)
		indices = tuple(start + i for i in indices)
		return PNFVertexList(self, start, vertex_amount, draw_mode, indices)

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

		self._draw_list_dirty = False
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

	def _regenerate_draw_list(self) -> None:
		dl, indices = DrawListBuilder(_INDEX_TYPE).build(self._top_groups, self._group_data)

		indices = (_C_TYPE_MAP[_INDEX_TYPE] * len(indices))(*indices)
		self._index_buffer = vertexbuffer.create_buffer(
			_GL_TYPE_SIZES[_INDEX_TYPE] * len(indices),
			gl.GL_ELEMENT_ARRAY_BUFFER,
			gl.GL_STATIC_DRAW,
		)
		self._index_buffer.set_data(indices)
		for dom in self._vertex_domains.values():
			for vao in dom._vaos.values():
				gl.glBindVertexArray(vao.value)
				gl.glBindBuffer(self._index_buffer.target, self._index_buffer.id)
				gl.glBindVertexArray(0)

		self._draw_list = dl
		self._draw_list_dirty = False

	def add(self, size, draw_mode, group, *data) -> PNFVertexList:
		raise NotImplementedError("yeah yeah")

	def add_indexed(self, size, draw_mode, group, indices, *data) -> PNFVertexList:
		attr_names = [x[0] if isinstance(x, tuple) else str(x) for x in data]
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

		return vtx_list

	def draw(self):
		if self._draw_list_dirty:
			self._regenerate_draw_list()

		self._index_buffer.bind()
		# print("/// DRAWING")
		for f in self._draw_list:
		#	print("  / Calling", f)
			f()
		#print("/// OK")

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
			for an, attr in v.attributes.items():
				r += f"  {an:<20}: {attr!r}\n"
				r += (" " * 22) + ": " + ' '.join(f"{b}" for b in (attr.c_type * 100)(*attr.gl_buffer.data[:100])) + "\n"
			r += "\n"

		r += f"\nIndex buffer: {' '.join(map(str, self._index_buffer.data))}"

		return r
