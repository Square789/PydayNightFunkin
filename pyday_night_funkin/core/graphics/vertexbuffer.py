"""
Custom vertexbuffers. Not only a more stripped-down and unsafe variant
of the ones found in `pyglet.graphics.vertexbuffer`, but also aware of
the type of data they store.
"""

#                              NOTE:                                  #
# A few safety checks are commented out to scrape a few nanoseconds   #
# off, as this module is only being used (and supposed to be used) by #
# internal graphics stuff and that behaves properly as far as I can   #
# tell.                                                               #
# Those comments are marked with "[UNSAFETY]".                        #


import ctypes
import typing as t

from pyglet.gl import gl

from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES, GL_TO_C_TYPE_MAP


class BufferObject:
	"""
	Python class wrapping an OpenGL buffer.
	"""

	def __new__(cls, *args, **kwargs):
		# Swallow args and kwargs as __new__ has to be called for cython stuff
		return super().__new__(cls)

	def __init__(
		self,
		target: int,
		size: int,
		usage: int = gl.GL_DYNAMIC_READ,
		gl_type: int = gl.GL_UNSIGNED_BYTE,
		count: int = 1,
	) -> None:
		self.id = gl.GLuint()
		self.target = target
		self.size = size
		"""Buffer size in bytes."""

		self.usage = usage
		self.type = gl_type
		"""OpenGL type of the data stored in this buffer."""

		self.c_type = GL_TO_C_TYPE_MAP[gl_type]
		self.c_type_size = GL_TYPE_SIZES[gl_type]

		if count < 1 or count > 4:
			raise ValueError("Attribute count must be in range 1..4")
		self.count = count
		"""Vertex attribute count. One of 1, 2, 3 or 4."""

		self.element_size = self.c_type_size * count
		"""
		Size of a single element in bytes, i. e. `2f` -> 8; `3B` -> 3.
		Default case is technically `1B` -> 1.
		"""

		gl.glCreateBuffers(1, self.id)
		gl.glNamedBufferData(self.id, size, None, usage)

	def set_size_and_data_array(self, size: int, data: ctypes.Array) -> None:
		"""
		Resizes the buffer to `size` bytes to accomodate the new data
		in the given array.
		The array may be taken ownership of by the BufferObject, copy
		it beforehand if needed.
		"""
		gl.glNamedBufferData(self.id, size, data, self.usage)
		self.size = size

	def set_data_py(self, start: int, size: int, data: t.Iterable) -> None:
		"""
		Sets the next `size` elements in the buffer from `start` to the
		data given in `data`, which is converted by passing it into a
		ctypes array of a type and size corresponding to this
		BufferObject's `c_type` and `count`.
		"""
		d = (self.c_type * (size * self.count))(*data)
		es = self.element_size
		self.set_data_array(es * start, es * size, d)

	def set_data_elements(self, start: int, count: int, data: ctypes.Array) -> None:
		"""
		Sets the next `count` elements (not bytes) from `start` of the
		underlying buffer to the data represented in the ctypes array.
		"""
		es = self.element_size
		self.set_data_array(es * start, es * count, data)

	def set_data_array(self, start: int, size: int, array: ctypes.Array):
		"""
		Sets the next `size` bytes starting from `start` to whatever is
		found in the given ctypes array.
		Unsafe and may easily segfault for bad starts and sizes.
		"""
		# [UNSAFETY]
		# `size` may not overrun the buffer's size, otherwise an
		# IndexError is raised.
		# """
		# if start < 0 or start + size > self.size:
		# 	raise IndexError(
		# 		f"Can not write {size} bytes from {start} into buffer of size {self.size}!"
		# 	)

		gl.glNamedBufferSubData(self.id, start, size, array)

	def get_data_elements(self, start: int, count: int) -> ctypes.Array:
		"""
		Reads at most `count` elements from `start` out of this
		attribute's buffer and returns it as a ctypes array of
		the buffer's attribute type. If not enough elements can be
		supplied, the returned buffer will be silently shrunk.
		"""
		el_size = self.element_size
		start_byte = start * el_size
		fetched_size = max(0, min(el_size * count, self.size - start_byte))
		fetched_elcount = fetched_size // el_size
		fetched_size = fetched_elcount * el_size

		res = (self.c_type * (fetched_elcount * self.count))()
		self._copy_data_into(start_byte, fetched_size, ctypes.addressof(res))
		return res

	def get_data_array(self, start: int, size: int) -> ctypes.Array:
		"""
		Retrieves the next `size` bytes from `start` and returns them
		in a ctypes ubyte array.
		May be truncated if `size` exceeds the buffer's size.
		"""
		fetched_size = max(0, min(size, self.size - start))
		res = (ctypes.c_ubyte * fetched_size)()
		self._copy_data_into(start, fetched_size, ctypes.addressof(res))
		return res

	def _copy_data_into(self, start: int, size: int, target: int) -> None:
		if size <= 0:
			return

		# [UNSAFETY]
		# if start < 0 or size < 0 or start + size > self.size:
		# 	raise ValueError("Invalid parameters for `_copy_data_into`.")

		ptr = gl.glMapNamedBufferRange(self.id, start, size, gl.GL_MAP_READ_BIT)
		ctypes.memmove(target, ptr, size)
		gl.glUnmapNamedBuffer(self.id)

	def bind(self, target: t.Optional[int] = None) -> None:
		"""
		Binds the buffer by binding it to the specified target or its
		standard `__init__`-given target.
		"""
		gl.glBindBuffer(self.target if target is None else target, self.id)

	def resize_elements(self, new_count: int) -> None:
		self.resize(self.element_size * new_count)

	def resize(self, new_size: int) -> None:
		"""
		Resizes the buffer to take `new_size` bytes. Will truncate
		existing data if the buffer shrunk.
		"""
		gl.glNamedBufferData(
			self.id,
			new_size,
			self.get_data_array(0, min(new_size, self.size)),
			self.usage,
		)
		self.size = new_size

	def ensure(self) -> None:
		"""
		Ensures that possibly pending data is uploaded to the GPU.
		"""
		pass

	def delete(self) -> None:
		"""Deletes the buffer on the OpenGL side."""
		gl.glDeleteBuffers(1, self.id)


class RAMBackedBufferObject(BufferObject):
	def __init__(
		self,
		target: int,
		size: int,
		usage: int = gl.GL_DYNAMIC_READ,
		data_gl_type: int = gl.GL_UNSIGNED_BYTE,
		data_count: int = 1,
	) -> None:
		super().__init__(target, size, usage, data_gl_type, data_count)

		self._ram_buffer = (ctypes.c_ubyte * size)()
		self._dirty = False
		self._dirty_min = 0
		self._dirty_max = 0

	def set_size_and_data_array(self, size: int, array: ctypes.Array) -> None:
		self._ram_buffer = array
		gl.glNamedBufferData(self.id, size, array, self.usage)
		self._dirty = False
		self.size = size

	def set_data_array(self, start: int, size: int, data_ptr: ctypes.Array) -> None:
		# [UNSAFETY]
		# if start < 0 or start + size > self.size:
		# 	return

		ctypes.memmove(
			ctypes.addressof(self._ram_buffer) + start,
			data_ptr,
			min(size, self.size - start),
		)
		if not self._dirty:
			self._dirty = True
			self._dirty_min = start
			self._dirty_max = start + size
		else:
			self._dirty_min = min(self._dirty_min, start)
			self._dirty_max = max(self._dirty_max, start + size)

	def _copy_data_into(self, start: int, size: int, target: int) -> None:
		ctypes.memmove(target, ctypes.addressof(self._ram_buffer) + start, size)

	def bind(self, target: t.Optional[int] = None) -> None:
		"""
		Binds the MappedBufferObject by uploading possibly pending
		data and then binding it to the specified target or its
		standard `__init__`-given target.
		"""
		self.ensure()
		super().bind(target)

	def resize(self, new_size: int) -> None:
		new = (ctypes.c_ubyte * new_size)()
		ctypes.memmove(new, self._ram_buffer, min(new_size, self.size))
		self._ram_buffer = new
		gl.glNamedBufferData(self.id, new_size, ctypes.addressof(self._ram_buffer), self.usage)
		self._dirty = False
		self.size = new_size

	def ensure(self) -> None:
		if not self._dirty:
			return

		gl.glNamedBufferSubData(
			self.id,
			self._dirty_min,
			self._dirty_max - self._dirty_min,
			ctypes.addressof(self._ram_buffer) + self._dirty_min,
		)

		self._dirty = False
