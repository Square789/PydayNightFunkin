
import ctypes
import typing as t

from pyglet.graphics import allocation, vertexarray, vertexbuffer
from pyglet.gl import gl

from pyday_night_funkin.core.graphics.shared import (
	C_TYPE_MAP, GL_TYPE_SIZES, RE_VERTEX_FORMAT, TYPE_MAP, USAGE_MAP
)

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram
	from pyday_night_funkin.core.graphics import PNFGroup


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


class PNFVertexList:
	"""
	Yet more intellectual property theft from pyglet, this bootleg
	vertex list tracks a position in a vertex buffer its vertices
	belong to and is passed to higher drawables for management of
	those.
	! WARNING ! Forgetting to call `delete` on vertex lists will leak
	memory in the list's domain.
	"""

	def __init__(
		self,
		vertex_domain: "PNFVertexDomain",
		domain_position: int,
		size: int,
		draw_mode: int,
		indices: t.Sequence[int],
	) -> None:
		self.domain = vertex_domain

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
		self.indices = tuple(domain_position + i for i in indices)
		"""
		Indices the vertex list's vertices should be drawn with.
		These are absolute to the vertex domain's buffers, so taking
		the example from `domain_position`'s docstring, [1, 2, 1] would
		be valid and [0, 1, 3] would not.
		"""

		self.deleted = False
		"""
		Whether this vertex list has been deleted and is effectively
		junk. Modify this and suffer the consequences; Use `delete()`
		to delete the vertex list!
		"""

	def delete(self):
		"""
		Tells this vertex domain this vertex list belongs to to
		free the space occupied by this list's vertices.
		After deletion, the vertex list should not be used anymore.
		"""
		if self.deleted:
			return

		self.domain.deallocate(self.domain_position, self.size)
		self.deleted = True

	def migrate(self, new_domain: "PNFVertexDomain") -> None:
		if self.domain.attributes.keys() != new_domain.attributes.keys():
			raise ValueError("Vertex domain attribute bundle mismatch!")

		new_start = new_domain.allocate(self.size)
		index_shift = -self.domain_position + new_start
		for k, cur_attr in self.domain.attributes.items():
			new_attr = new_domain.attributes[k]
			cur_attr.get_region(self.domain_position, self.size).array[:] = \
				new_attr.get_region(new_start, self.size).array[:]

		self.domain.deallocate(self.domain_position, self.size)
		self.domain = new_domain
		self.domain_position = new_start
		self.indices = tuple(i + index_shift for i in self.indices)

	def __getattr__(self, name: str) -> t.Any:
		att = self.domain.attributes[name]

		region = att.get_region(self.domain_position, self.size)
		region.invalidate()
		return region.array

	def __setattr__(self, name: str, value: t.Any) -> None:
		if "domain" in self.__dict__ and name in self.__dict__["domain"].attributes:
			self.__getattr__(name)[:] = value
		else:
			super().__setattr__(name, value)


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

		self.gl_buffer = vertexbuffer.create_buffer(self.buffer_size, usage=usage)

	def get_region(self, start: int, size: int) -> vertexbuffer.BufferObjectRegion:
		"""
		Returns a buffer object region over the area of `size` vertices
		occupying this vertex domain attribute's buffer starting at
		vertex `start`.
		"""
		region = self.gl_buffer.get_region(
			self.element_size * start,
			self.element_size * size,
			ctypes.POINTER(self.c_type * (size * self.count)),
		)
		region.invalidate()
		return region

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
		usage = USAGE_MAP[usage]

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
			# in the vertex list
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
		Tries to safely allocate `size` vertices.
		"""
		try:
			return self._allocator.alloc(size)
		except allocation.AllocatorMemoryException:
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

	def create_vertex_list(
		self, vertex_amount: int, group: "PNFGroup", draw_mode: int, indices: t.Sequence[int]
	) -> PNFVertexList:
		"""
		Creates and returns a vertex list in the domain for the
		given group.
		"""
		self.ensure_vao(group.program)
		start = self.allocate(vertex_amount)
		return PNFVertexList(self, start, vertex_amount, draw_mode, indices)
