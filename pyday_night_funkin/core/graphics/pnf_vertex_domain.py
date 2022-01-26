
import ctypes
import typing as t

from pyglet.graphics import allocation, vertexarray, vertexbuffer
from pyglet.gl import gl
from pyday_night_funkin.core.graphics.interfacer import PNFBatchInterfacer

from pyday_night_funkin.core.graphics.shared import (
	C_TYPE_MAP, GL_TYPE_SIZES, RE_VERTEX_FORMAT, TYPE_MAP, USAGE_MAP
)
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject, MappedBufferObject

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram
	from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup


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


class PNFVertexDomainAttribute:
	"""
	Class representing the vertex attribute of a domain.
	Contains a buffer for the attribute's data.
	"""

	def __init__(
		self,
		binding_point: int,
		count: int,
		type_: int,
		normalize: int,
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
		self.c_type = C_TYPE_MAP[type_]
		self.element_size = GL_TYPE_SIZES[type_] * count
		"""
		Size of a single attribute in bytes, i. e. `2f` -> 8; `3B` -> 3
		"""

		self.buffer_size = self.element_size * PNFVertexDomain.INITIAL_VERTEX_CAPACITY
		"""Size of this attribute's OpenGL buffer, in bytes."""

		self.normalize = normalize
		self.usage = usage

		self.gl_buffer = MappedBufferObject(gl.GL_ARRAY_BUFFER, self.buffer_size, usage)

	def set_data(self, start: int, size: int, data) -> None:
		cdata = (self.c_type * (size * self.count))(*data)
		self.set_raw_data(start, size, cdata)

	def set_raw_data(self, start: int, size: int, data) -> None:
		self.gl_buffer.set_data(self.element_size * start, self.element_size * size, data)

	def get_data(self, start, size) -> ctypes.Array:
		return self.gl_buffer.get_data(self.element_size * start, self.element_size * size)

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

	def __init__(self, attribute_bundle: "frozenset[str]") -> None:
		"""
		Creates a new vertex domain.
		`attribute_bundle` should be an iterable of valid vertex attribute
		format strings.
		"""
		# NOTE: This allocator does not track bytes, but only vertices.
		self.attributes: t.Dict[str, PNFVertexDomainAttribute] = {}
		self.attribute_bundle = attribute_bundle
		"""Attribute bundle the domain was created with."""

		self._allocator = allocation.Allocator(self.INITIAL_VERTEX_CAPACITY)
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

	def _parse_attribute(self, attr: str) -> t.Tuple[str, int, int, int, int]:
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
		type_ = TYPE_MAP[type_]
		normalize = gl.GL_TRUE if norm else gl.GL_FALSE
		usage = USAGE_MAP[usage or "dynamic"]

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

		vao_id = gl.GLuint()
		gl.glCreateVertexArrays(1, ctypes.byref(vao_id))

		for shader_attr in shader.attributes.values():
			# Attributes are linked with shaders by their name as passed
			# in the add call
			if shader_attr.name not in self.attributes:
				raise ValueError(
					f"Shader program {shader.id!r} contained vertex attribute {shader_attr},"
					f"but {self.__class__.__name__} does not know {shader_attr.name!r}."
				)
			attr = self.attributes[shader_attr.name]

			gl.glBindVertexArray(vao_id)
			attr.gl_buffer.bind()
			gl.glEnableVertexArrayAttrib(vao_id, shader_attr.location)
			gl.glVertexAttribPointer(
				shader_attr.location, attr.count, attr.type, attr.normalize, 0, 0
			)
			gl.glBindVertexArray(0)

			#bp = attr.binding_point
			#gl.glVertexArrayVertexBuffer(vao_id, bp, attr.gl_buffer.id, 0, attr.element_size)
			#gl.glVertexArrayAttribBinding(vao_id, shader_attr.location, bp)
			#gl.glVertexArrayAttribFormat(vao_id, bp, attr.count, attr.type, attr.normalize, 0)

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
		gl.glBindVertexArray(vao)
		self._active_vao = vao

	def unbind_vao(self) -> None:
		"""
		Unbinds the active VAO.
		"""
		gl.glBindVertexArray(0)
		self._active_vao = None

	def allocate(self, size: int) -> int:
		"""
		Tries to safely allocate `size` vertices, resizing as
		necessary.
		May raise `pyglet.graphics.allocation.AllocatorMemoryException`.
		"""
		try:
			return self._allocator.alloc(size)
		except allocation.AllocatorMemoryException:
			pass
		new_size = max(nearest_pow2(self._allocator.capacity + 1), nearest_pow2(size))
		self._resize(new_size)
		return self._allocator.alloc(size)

	def deallocate(self, start: int, size: int) -> None:
		"""
		Deallocates `size` vertices starting from `start`.
		"""
		self._allocator.dealloc(start, size)

	def _resize(self, new_size: int) -> None:
		# The buffers in `self.attributes` can always hold `self._allocator.capacity`
		# vertices. Resize them if needed.
		self._allocator.set_capacity(new_size)
		for attr in self.attributes.values():
			attr.resize(new_size)

	def create_interfacer(
		self,
		vertex_amount: int,
		batch: "PNFBatch",
		group: "PNFGroup",
		draw_mode: int,
		indices: t.Sequence[int],
	) -> PNFBatchInterfacer:
		"""
		Creates and returns an interfacer in the domain for the
		given group.
		"""
		self.ensure_vao(group.state.program)
		start = self.allocate(vertex_amount)
		return PNFBatchInterfacer(self, start, vertex_amount, draw_mode, indices, batch)
