
from collections import defaultdict
import ctypes
import re
import typing as t

from loguru import logger
from pyglet.gl import gl
from pyglet.graphics import allocation, vertexarray, vertexbuffer

if t.TYPE_CHECKING:
	from pyglet.graphics import Group



INDEX_TYPE = gl.GLuint

class GroupData:
	__slots__ = ("vertex_domain", "children")

	def __init__(
		self,
		vertex_domain: t.Optional["PNFVertexDomain"] = None,
		children: t.Sequence[Group] = (),
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


RE_VERTEX_FORMAT = re.compile("(.*)(\d)(.)/(static|dynamic|stream)")

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

_USAGE_MAP = {
	"static": gl.GL_STATIC_DRAW,
	"dynamic": gl.GL_DYNAMIC_DRAW,
	"stream": gl.GL_STREAM_DRAW,
}


def _parse_vertex_data(data):
	res = []
	for block in data:
		if not isinstance(block, str):
			name = block
			ini_data = None
		else:
			name = block[0]
			ini_data = block[1]
		res.append((name, ini_data))

	return res

class PNFGroup:
	def __init__(
		self,
		program,

	) -> None:
		self.program = program


class PNFVertexList:
	"""
	Yet more intellectual property theft from pyglet, this bootleg
	vertex list tracks a position in a vertex buffer its vertices
	belong to and is passed to higher drawables for management of
	those.
	"""

	def __init__(self, batch, group) -> None:
		self.batch = batch
		self.group = group

	def delete(self):
		pass


class PNFVertexDomain:
	"""
	Somewhat identical to pyglet's VertexDomain, a PNFVertexDomain
	keeps several buffers for bundles of vertex attributes.
	It additionally has a VAO to quickly (?) set them up.
	The vertex layout shouldn't ever need to be changed.
	"""

	def __init__(self, attribute_bundle: t.Sequence[str]) -> None:
		self._attributes = {}
		for attr in attribute_bundle:
			buf = vertexbuffer.create_buffer(4096)
			name, count, fmt, usage = self._parse_attribute(attr)
			self._attributes[name] = (buf, count, fmt, usage)

		self.vao = vertexarray.VertexArray()
		with self.vao:
			for i, (name, (count, fmt, usage)) in enumerate(self._attributes.items()):
				gl.glEnableVertexAttribArray(i)
				gl.glVertexArrayAttribBinding

	def _parse_attribute(self, attr: str) -> t.Tuple[str, int, int, int]:
		if (re_res := RE_VERTEX_FORMAT.match(attr)) is None:
			raise ValueError(f"Invalid attribute format string {attr!r}")
		name, count, fmt, usage = re_res.groups()

		count = int(count)
		fmt = _TYPE_MAP[fmt]
		usage = _USAGE_MAP[usage]

		if count not in range(1, 5):
			raise ValueError(f"Vertex attribute count must be 1, 2, 3 or 4; was {count}!")

		return (name, count, fmt, usage)

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

	def _add_group(self, group):
		if group.parent is None:
			self._top_groups.append(group)
		else:
			if group.parent not in self._group_data:
				self._add_group(group.parent)
			self._group_data[group.parent].children.append(group)

		self._draw_list_dirty = True

	def _get_vertex_domain(self, parsed_data):
		"""
		Get an existing or newly created vertexdomain for the given
		vertex attribute bundle.
		"""
		attr_bundle = tuple(name for name, _ in parsed_data)
		if attr_bundle not in self._vertex_domains:
			self._vertex_domains[attr_bundle] = PNFVertexDomain()

		return self._vertex_domains[attr_bundle]

	def _regenerate_draw_list(self):
		for grp in sorted(self._top_groups):
			pass

	def add(self, vertex_amount, draw_mode, group, *data) -> PNFVertexList:
		raise NotImplementedError("yeah yeah")

	def add_indexed(self, vertex_amount, draw_mode, group, indices, *data) -> PNFVertexList:
		data = _parse_vertex_data(data)
		self._add_group(group)
		vtxd = self._get_vertex_domain(data)
		self._group_data[group].vertex_domain = vtxd

		vtx_list = PNFVertexList(self, group, vtxd)
		for _, ini_data in data:
			if ini_data is None:
				continue
			vtx_list.set_attribute()

	def draw(self):
		if self._draw_list_dirty:
			self._regenerate_draw_list()

		for f in self._draw_list:
			f()

	def draw_subset(self) -> None:
		raise NotImplementedError()
