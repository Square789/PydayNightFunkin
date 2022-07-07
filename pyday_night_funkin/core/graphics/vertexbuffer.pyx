
from libc.stdint cimport *
from libc.stdio cimport printf
from libc.stdlib cimport calloc, malloc, realloc, free
from libc.string cimport memcpy, memmove, memset

from pyday_night_funkin.core.graphics.cygl.gl cimport *

import ctypes

from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES, GL_TO_C_TYPE_MAP


include "vertexbuffer_pyobj_extractors.pxi"

cdef GLRegistry *gl = NULL

cdef void *_get_ctypes_data_ptr(object arr) except NULL:
	return <void *><size_t>ctypes.addressof(arr)

cdef class BufferObject:
	cdef uint8_t buffer_exists
	cdef readonly GLuint id
	cdef readonly GLenum target
	cdef readonly GLsizeiptr size
	cdef readonly GLenum usage
	cdef readonly GLenum type
	cdef readonly object c_type
	cdef readonly uint8_t count
	cdef readonly size_t element_size
	cdef FPTR_pyobj_extractor pyobj_extractor

	def __init__(self, *_, **__):
		# __cinit__ does everything.
		# I don't think that's how you are meant to do it, but whatever it works.
		# This __init__ method ignores all args and kwargs in order to make switching
		# this thing for the pure python versions easy.
		pass

	def __cinit__(
		self,
		GLenum target,
		GLsizeiptr size,
		GLenum usage = GL_DYNAMIC_READ,
		GLenum gl_type = GL_UNSIGNED_BYTE,
		uint8_t count = 1,
	):
		global gl
		if gl == NULL:
			gl = cygl_get_reg()

		self.buffer_exists = False
		self.target = target
		self.size = size
		self.usage = usage
		self.type = gl_type
		self.c_type = GL_TO_C_TYPE_MAP[gl_type]

		if count not in (1, 2, 3, 4):
			raise ValueError("Attribute count must be in range 1..4")
		self.count = count

		self.element_size = cygl_get_gl_type_size(gl_type) * count
		if self.element_size == 0:
			raise ValueError(
				f"Element size of buffer with gl type {gl_type} and count {count} "
				f"ended up being 0! Type is likely not recognized."
			)

		self.pyobj_extractor = get_pyobj_extractor_function(gl_type)
		if self.pyobj_extractor == NULL:
			raise ValueError("Could not find extractor function for gl type {gl_type}!")

		gl.CreateBuffers(1, &self.id); cygl_errcheck()
		self.buffer_exists = True
		gl.NamedBufferData(self.id, size, NULL, usage); cygl_errcheck()

	def __dealloc__(self):
		# Would call `delete`, but cython says to not do that from __dealloc__.
		# Yaaay, code duplication.
		if self.buffer_exists:
			gl.DeleteBuffers(1, &self.id)
			self.buffer_exists = False

	cpdef set_size_and_data_array(self, GLsizeiptr size, object data):
		self.set_size_and_data_raw(size, _get_ctypes_data_ptr(data))

	cdef uint8_t set_size_and_data_raw(self, GLsizeiptr size, void *data) except 1:
		gl.NamedBufferData(self.id, size, data, self.usage)
		cygl_errcheck()
		self.size = size
		return 0

	cpdef set_data_py(self, GLintptr start, GLsizeiptr size, object data):
		cdef size_t byte_size = size * self.element_size
		cdef void *converted_array = malloc(byte_size)
		if converted_array == NULL:
			raise MemoryError()

		try:
			self.pyobj_extractor(size * self.count, converted_array, data)
		except:
			free(converted_array)
			raise

		try:
			self.set_data_raw(start * self.element_size, byte_size, converted_array)
		finally:
			free(converted_array)

	cpdef set_data_elements(self, GLintptr start, GLsizeiptr size, object data):
		self.set_data_raw(
			self.element_size * start,
			self.element_size * size,
			_get_ctypes_data_ptr(data),
		)

	cpdef set_data_array(self, GLintptr start, GLsizeiptr size, object data):
		self.set_data_raw(start, size, _get_ctypes_data_ptr(data))

	cdef uint8_t set_data_raw(self, GLintptr start, GLsizeiptr size, void *data) except 1:
		gl.NamedBufferSubData(self.id, start, size, data)
		cygl_errcheck()
		return 0

	cpdef object get_data_elements(self, GLintptr start, size_t count):
		cdef size_t start_byte = start * self.element_size
		cdef GLsizeiptr fetched_size = max(
			0,
			min(
				# These casts are probably so very wrong
				<int64_t>self.element_size * <int64_t>count,
				<int64_t>self.size - <int64_t>start_byte,
			),
		)
		cdef size_t fetched_elcount = fetched_size // self.element_size
		fetched_size = fetched_elcount * self.element_size

		res = (self.c_type * (fetched_elcount * self.count))()
		self._copy_data_into(start_byte, fetched_size, _get_ctypes_data_ptr(res))
		return res

	cpdef object get_data_array(self, GLintptr start, size_t size):
		cdef GLsizeiptr fetched_size = min(size, self.size - start)
		res_buffer = (ctypes.c_ubyte * fetched_size)()
		self._copy_data_into(start, fetched_size, _get_ctypes_data_ptr(res_buffer))
		return res_buffer

	cdef uint8_t _copy_data_into(self, GLintptr start, GLsizeiptr size, void *target) except 1:
		if size == 0:
			return 0

		cdef void *ptr = gl.MapNamedBufferRange(self.id, start, size, GL_MAP_READ_BIT)
		cygl_errcheck()
		memcpy(target, ptr, size)
		gl.UnmapNamedBuffer(self.id)
		cygl_errcheck()
		return 0

	cpdef bind(self, GLenum target = 0):
		gl.BindBuffer(self.target if target == 0 else target, self.id)
		cygl_errcheck()

	cpdef resize_elements(self, GLsizeiptr new_count):
		self.resize(self.element_size * new_count)

	cpdef resize(self, GLsizeiptr new_size):
		my_data = self.get_data_array(0, min(new_size, self.size))
		gl.NamedBufferData(self.id, new_size, _get_ctypes_data_ptr(my_data), self.usage)
		del my_data
		cygl_errcheck()

	cpdef ensure(self):
		pass

	cpdef delete(self):
		if self.buffer_exists:
			gl.DeleteBuffers(1, &self.id); cygl_errcheck()
			self.buffer_exists = False


cdef class RAMBackedBufferObject(BufferObject):
	cdef uint8_t *_ram_buffer
	cdef uint8_t dirty
	cdef GLintptr dirty_min
	cdef GLintptr dirty_max

	def __cinit__(
		self,
		GLenum target,
		GLsizeiptr size,
		*_args,
		**_kwargs,
	):
		self._ram_buffer = <uint8_t *>calloc(sizeof(uint8_t), size)
		if self._ram_buffer == NULL:
			raise MemoryError()

		self.dirty = False
		self.dirty_min = 0
		self.dirty_max = 0

	def __dealloc__(self):
		free(self._ram_buffer)

	cdef uint8_t set_size_and_data_raw(self, GLsizeiptr size, void *data) except 1:
		free(self._ram_buffer)
		self._ram_buffer = <uint8_t *>malloc(sizeof(uint8_t) * size)
		if self._ram_buffer == NULL:
			raise MemoryError()

		memcpy(self._ram_buffer, data, size)
		BufferObject.set_size_and_data_raw(self, size, data)
		self.dirty = False
		self.size = size
		return 0

	cdef uint8_t set_data_raw(self, GLintptr start, GLsizeiptr size, void *data) except 1:
		memmove(
			self._ram_buffer + start,
			data,
			min(<GLintptr>size, <GLintptr>self.size - start),
		)
		if not self.dirty:
			self.dirty = True
			self.dirty_min = start
			self.dirty_max = start + size
		else:
			self.dirty_min = min(self.dirty_min, start)
			self.dirty_max = max(self.dirty_max, <GLintptr>(start + size))
		return 0

	cdef uint8_t _copy_data_into(self, GLintptr start, GLsizeiptr size, void *target) except 1:
		memcpy(target, self._ram_buffer + start, size)
		return 0

	cpdef bind(self, GLenum target = 0):
		self.ensure()
		BufferObject.bind(self, target)

	cpdef resize(self, GLsizeiptr new_size):
		cdef uint8_t *new_ptr = <uint8_t *>realloc(self._ram_buffer, new_size)
		if new_ptr == NULL:
			# self._ram_buffer is probably gonna be freed by __dealloc__
			raise MemoryError()

		if self.size < new_size:
			memset(new_ptr + self.size, 0, self.size - new_size)

		self._ram_buffer = new_ptr
		gl.NamedBufferData(self.id, new_size, self._ram_buffer, self.usage)
		cygl_errcheck()
		self.dirty = False
		self.size = new_size

	cpdef ensure(self):
		if not self.dirty:
			return

		gl.NamedBufferSubData(
			self.id,
			self.dirty_min,
			self.dirty_max - self.dirty_min,
			self._ram_buffer + self.dirty_min,
		)
		cygl_errcheck()
		self.dirty = False
