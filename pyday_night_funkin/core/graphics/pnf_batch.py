
from collections import defaultdict
import ctypes
import re
import typing as t

from loguru import logger
from pyglet.gl import gl
from pyglet.graphics import allocation, vertexarray, vertexbuffer

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram
	from .pnf_group import PNFGroup


INDEX_TYPE = gl.GLuint

class GroupData:
	__slots__ = ("vertex_domain", "children")

	def __init__(
		self,
		vertex_domain: t.Optional["PNFVertexDomain"] = None,
		children: t.Sequence["PNFGroup"] = (),
	) -> None:
		self.vertex_domain = vertex_domain
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


class MemoryManagedBuffer:
	"""
	Composite class holding a pyglet allocator and a vertexbuffer.
	Exposes just the buffer operations needed.
	"""

	def __init__(self, capacity: int = 65536, *args, **kwargs) -> None:
		"""
		Initializes a MemoryManagedBuffer. Will pass through all
		args and kwargs to `vertexbuffer.create_buffer`.
		"""
		self._buffer = vertexbuffer.create_buffer(capacity, *args, **kwargs)
		self._allocator = allocation.Allocator(capacity)

	def safe_alloc(self, size: int) -> int:
		"""
		Effectively stolen from vertexdomain's `safe_alloc` method,
		it tries to get a fitting starting region from the allocator and -
		should that fail - resizes both the allocator and its buffer and
		retries the allocation.
		"""
		try:
			return self._allocator.alloc(size)
		except allocation.AllocatorMemoryException as exc:
			new_size = nearest_pow2(exc.requested_capacity)
			self._buffer.resize(new_size * ctypes.sizeof(INDEX_TYPE))
			self._allocator.set_capacity(new_size)
			return self._allocator.alloc(size)

	def set_data_region(self, data: ctypes.pointer, start: int, length: int) -> None:
		"""
		Sets the buffer's data to the given data from `start` for
		`length` bytes.
		"""
		# NOTE: Involves memmove and a technically unnecessary duplication of data,
		# but workarounds are annoying and probably not that worth it
		self._buffer.set_data_region(data, start, length)

	def map(self, invalidate: bool = False) -> ctypes.pointer:
		return self._buffer.map(invalidate)

	def unmap(self) -> None:
		return self._buffer.unmap()

	def delete(self) -> None:
		self._buffer.delete()
		self._buffer = self._allocator = None

	@property
	def id(self) -> int:
		return self._buffer.id


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
		start: int,
		amount: int,
	) -> None:
		self.vtxd = vertex_domain
		self.start = start
		self.amount = amount

	def __getattr__(self, name: str) -> t.Any:
		return []

	def __setattr__(self, name: str, value: t.Any) -> None:
		super().__setattr__(name, value)

	def delete(self):
		pass


class PNFVertexDomainAttribute:
	def __init__(
		self,
		gl_buffer_id: int,
		count: int,
		type_: int,
		normalize: bool,
		usage: int,
	) -> None:
		self.gl_buffer_id = gl_buffer_id
		self.count = count
		self.type = type_
		self.normalize = normalize
		self.usage = usage
		self.buffer_dirty = False

		self.system_buffer = (ctypes.c_ubyte * _GL_TYPE_SIZES[type_])()

	def set_data(self) -> None:
		pass

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} gl_buffer_id={self.gl_buffer_id} count={self.count} "
			f"type={self.type} normalize={self.normalize} usage={self.usage} at 0x{id(self):>016X}>"
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

	def __init__(self, attribute_bundle: t.Sequence[str]) -> None:
		"""
		Creates a new vertex domain.
		`attribute_bundle` should be a sequence of valid vertex attribute
		format strings.
		"""
		self._attributes: t.Dict[str, PNFVertexDomainAttribute] = {}
		self._vaos: t.Dict[int, vertexarray.VertexArray] = {}

		for attr in attribute_bundle:
			gl_buf = MemoryManagedBuffer(4096)
			name, *ctnu = self._parse_attribute(attr)
			self._attributes[name] = PNFVertexDomainAttribute(gl_buf.id, *ctnu)

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

		vao = vertexarray.VertexArray()
		with vao:
			for shader_attr in shader.attributes.values():
				# Attributes are linked with shaders by their name as passed
				# in the vertex list
				if shader_attr.name not in self._attributes:
					raise ValueError(
						f"Shader program {shader.id!r} contained vertex attribute {shader_attr},"
						f"but {self.__class__.__name__} does not know {shader_attr.name!r}."
					)
				attr = self._attributes[shader_attr.name]

				# NOTE: This may be replacable with the newer glVertexAttribFormat and
				# glBindVertexBuffers!

				# glVertexAttribPointer depends on this binding
				gl.glBindBuffer(gl.GL_ARRAY_BUFFER, attr.gl_buffer_id)
				gl.glEnableVertexAttribArray(shader_attr.location)
				gl.glVertexAttribPointer(
					shader_attr.location, attr.count, attr.type, gl.GL_FALSE, 0, 0
				)

		# WARNING: Should shaders be deleted and their ids reassigned,
		# this may fail in disgusting ways
		self._vaos[shader.id] = vao

	def allocate(self, size: int):
		"""
		Tries to safely allocate `size` vertices.
		"""

	def create_vertex_list(self, vertex_amount: int, group: "PNFGroup") -> PNFVertexList:
		self.ensure_vao(group.program)
		return PNFVertexList(self, 0, 0)


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

		self._vertex_domains = {}

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
		def visit(group: "PNFGroup", n: int = 0) -> None:
			logger.debug((" " * n) + f"Yooo {group}")
			for sub_group in self._group_data[group].children:
				visit(sub_group, n + 1)

		for group in sorted(self._top_groups):
			visit(group)

		self._draw_list_dirty = False

	def add(self, vertex_amount, draw_mode, group, *data) -> PNFVertexList:
		raise NotImplementedError("yeah yeah")

	def add_indexed(self, vertex_amount, draw_mode, group, indices, *data) -> PNFVertexList:
		attr_names = [x[0] if isinstance(x, tuple) else str(x) for x in data]
		self._add_group(group)
		vtxd = self._get_vertex_domain(attr_names)
		self._group_data[group].vertex_domain = vtxd

		vtx_list = vtxd.create_vertex_list(vertex_amount, group)
		return vtx_list

	def draw(self):
		if self._draw_list_dirty:
			self._regenerate_draw_list()

		for f in self._draw_list:
			f()

	def draw_subset(self) -> None:
		raise NotImplementedError()

	def migrate(self, *args, **kwargs) -> None:
		raise NotImplementedError("shut up pls")
