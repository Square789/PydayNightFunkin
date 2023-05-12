
import ctypes
import typing as t

from pyglet.gl import gl

from pyday_night_funkin.core.graphics import allocation
from pyday_night_funkin.core.graphics.shared import (
	GL_TYPE_SIZES, RE_VERTEX_FORMAT, TYPECHAR_TO_GL_TYPE_MAP, USAGE_MAP
)
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject, RAMBackedBufferObject
from pyday_night_funkin.core.utils import dump_id

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram
	from pyday_night_funkin.core.graphics.pnf_batch import DrawList


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


class PNFVertexDomainAttribute(RAMBackedBufferObject):
	"""
	Class representing the vertex attribute of a domain.
	"""

	def __init__(
		self,
		binding_point: int,
		count: int,
		type_: int,
		normalize: int,
		usage: int,
	) -> None:
		self.binding_point = binding_point
		"""
		Binding point the attribute should be bound to. This is NOT the
		shader location!
		"""

		self.normalize = normalize
		"""
		Whether to normalize the data in this vertex attribute to the
		range between 0 and 1.
		This will for example cause a value of 127 to become 0.5 in the
		shader, with OpenGL being aware of the data type
		`UNSIGNED_BYTE`. Otherwise it would end up being 127.0, quickly
		breaking calculations.
		"""

		# The vertexbuffer also calculates this, which is ugly but what can you do
		ini_bytes = GL_TYPE_SIZES[type_] * count * PNFVertexDomain.INITIAL_VERTEX_CAPACITY
		super().__init__(gl.GL_ARRAY_BUFFER, ini_bytes, usage, type_, count)

	def __new__(
		cls,
		binding_point: int,
		count: int,
		type_: int,
		normalize: int,
		usage: int,
	):
		ini_bytes = GL_TYPE_SIZES[type_] * count * PNFVertexDomain.INITIAL_VERTEX_CAPACITY
		return super().__new__(cls, gl.GL_ARRAY_BUFFER, ini_bytes, usage, type_, count)

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} (OpenGL buffer id {self.id}) "
			f"count={self.count} type={self.type} normalize={self.normalize} usage={self.usage} "
			f"at {dump_id(self)}>"
		)


class PNFVertexDomain:
	"""
	Somewhat identical to pyglet's VertexDomain, a PNFVertexDomain
	keeps several buffers for bundles of vertex attributes.
	Practically, there should only be a few vertex domains in existence,
	the most prevalent one managing all sprites.

	Vertex domains have VAOs for different combinations of programs
	and draw lists to quickly set up vertex bindings.
	The vertex attribute bundle is unchangable.
	"""

	INITIAL_VERTEX_CAPACITY = 2048

	def __init__(self, attribute_bundle: "frozenset[str]") -> None:
		"""
		Creates a new vertex domain.
		`attribute_bundle` should be an iterable of valid vertex attribute
		format strings.
		"""
		self.attributes: t.Dict[str, PNFVertexDomainAttribute] = {}
		self.attribute_bundle = attribute_bundle
		"""Attribute bundle the domain was created with."""

		# NOTE: This allocator does not track bytes, but vertices.
		self._allocator = allocation.Allocator(self.INITIAL_VERTEX_CAPACITY)
		self._vaos: t.Dict[t.Hashable, t.Dict[int, gl.GLuint]] = {}
		"""
		Maps each shader id and draw list to a VAO that links the
		vertex domain's attributes to the shader's inputs when bound.
		"""

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
		type_ = TYPECHAR_TO_GL_TYPE_MAP[type_]
		normalize = gl.GL_TRUE if norm else gl.GL_FALSE
		usage = USAGE_MAP[usage or "dynamic"]

		if count not in range(1, 5):
			raise ValueError(f"Vertex attribute count must be 1, 2, 3 or 4; was {count}!")

		return (name, count, type_, normalize, usage)

	def ensure_vao(self, shader: "ShaderProgram", draw_list: "DrawList") -> None:
		"""
		If no VAO for this shader/draw list combination has been
		created yet, sets up all attribute bindings for this vertex
		domain's managed attribute bundle in context of the given
		shader program and stores them in an internal VAO for future
		use.
		"""
		if draw_list.name not in self._vaos:
			self._vaos[draw_list.name] = {}

		vao_dict = self._vaos[draw_list.name]
		if shader.id in vao_dict:
			return

		vao_id = gl.GLuint()
		gl.glCreateVertexArrays(1, ctypes.byref(vao_id))

		for shader_attr_name, shader_attr_dict in shader.attributes.items():
			# Attributes are linked with shaders by their name as passed
			# in the add call
			if shader_attr_name not in self.attributes:
				raise ValueError(
					f"Shader program {shader.id!r} contained vertex attribute "
					f"{shader_attr_name!r}, but {self.__class__.__name__} does not know "
					f"{shader_attr_name!r}."
				)
			attr = self.attributes[shader_attr_name]
			bp = attr.binding_point
			loc = shader_attr_dict["location"]
			# Set index/element buffer
			gl.glVertexArrayElementBuffer(vao_id, draw_list.index_buffer.id)
			# Enable the shader location / attribute index
			gl.glEnableVertexArrayAttrib(vao_id, loc)
			# Specify vertex layout for the attribute at index `loc`
			gl.glVertexArrayAttribFormat(vao_id, loc, attr.count, attr.type, attr.normalize, 0)
			# Associate the binding point with the buffer vertices should be sourced from.
			gl.glVertexArrayVertexBuffer(vao_id, bp, attr.id, 0, attr.element_size)
			# Link the shader attribute index with the binding point
			gl.glVertexArrayAttribBinding(vao_id, loc, bp)

		# WARNING: Should shaders be deleted and their ids reassigned,
		# this may fail in disgusting ways
		vao_dict[shader.id] = vao_id

	def bind_vao(self, program: "ShaderProgram", draw_list_name: t.Hashable) -> None:
		"""
		Binds the VAO for the program using the given draw list's
		index buffer.
		Remember to call `gl.glBindVertexArray(0)` before calling
		**any** vertex gl functions afterwards, otherwise it will be
		erroneously affected.
		Raises `KeyError` if `ensure_vao` was never called for the
		given program.
		"""
		gl.glBindVertexArray(self._vaos[draw_list_name][program.id])

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

	def delete(self) -> None:
		"""
		Deletes all vertex buffers and VAOs of this domain.
		"""
		for attr in self.attributes.values():
			attr.delete()

		vao_ids: t.List[gl.GLuint] = [id_ for vaos in self._vaos.values() for id_ in vaos.values()]
		vao_count = len(vao_ids)
		gl.glDeleteVertexArrays(vao_count, (gl.GLuint * vao_count)(*vao_ids))

	def _resize(self, new_size: int) -> None:
		# The buffers in `self.attributes` can always hold `self._allocator.capacity`
		# vertices. Resize them if needed.
		self._allocator.set_capacity(new_size)
		for attr in self.attributes.values():
			attr.resize_elements(new_size)
