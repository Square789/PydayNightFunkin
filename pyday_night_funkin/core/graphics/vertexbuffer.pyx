
from libc.stdint cimport *
from libc.stdio cimport printf
from libc.stdlib cimport malloc, realloc, free
from libc.string cimport memcpy, memmove, memset

from pyday_night_funkin.core.graphics.cygl.gl cimport *

import ctypes


cdef GLRegistry *gl = NULL

cdef void *_get_ctypes_data_ptr(object arr):
	return <void *><size_t>ctypes.addressof(arr)


cdef class BufferObject:
	cdef readonly GLuint id
	cdef GLenum usage
	cdef GLenum target
	cdef GLsizeiptr size
	cdef uint8_t buffer_exists

	def __cinit__(self, GLenum target, GLsizeiptr size, GLenum usage = 0):
		global gl
		if gl is NULL:
			gl = cygl_get_reg()

		if usage == 0:
			usage = GL_DYNAMIC_READ

		self.buffer_exists = False
		self.usage = usage
		self.target = target
		self.size = size

		gl.CreateBuffers(1, &self.id); cygl_errcheck()
		self.buffer_exists = True
		gl.NamedBufferData(self.id, size, NULL, usage); cygl_errcheck()

	def __dealloc__(self):
		# Would call `delete`, but cython says to not do that from __dealloc__.
		# Yaaay, code duplication.
		if self.buffer_exists:
			gl.DeleteBuffers(1, &self.id)
			self.buffer_exists = False

	# TODO const void *alternatives that don't pass around ctypes arrays
	cpdef set_size_and_data(self, GLsizeiptr size, object data):
		gl.NamedBufferData(self.id, size, _get_ctypes_data_ptr(data), self.usage,
		)
		cygl_errcheck()
		self.size = size

	cpdef set_data(self, GLintptr start, GLsizeiptr size, object data):
		gl.NamedBufferSubData(self.id, start, size, _get_ctypes_data_ptr(data))
		cygl_errcheck()

	cpdef object get_data(self, GLintptr start, size_t size):
		cdef GLsizeiptr fetched_size = min(size, self.size - start)
		res_buffer = (ctypes.c_ubyte * fetched_size)()
		if fetched_size == 0:
			return res_buffer

		cdef uint8_t *data = <uint8_t *>gl.MapNamedBufferRange(
			self.id,
			start,
			fetched_size,
			GL_MAP_READ_BIT,
		)
		cygl_errcheck()

		memcpy(_get_ctypes_data_ptr(res_buffer), data, fetched_size)
		gl.UnmapNamedBuffer(self.id); cygl_errcheck()
		return res_buffer

	cpdef bind(self, GLenum target = 0):
		gl.BindBuffer(self.target if target == 0 else target, self.id); cygl_errcheck()

	cpdef resize(self, GLsizeiptr new_size):
		my_data = self.get_data(0, min(new_size, self.size))
		gl.NamedBufferData(self.id, new_size, _get_ctypes_data_ptr(my_data), self.usage)
		del my_data
		cygl_errcheck()

	cpdef ensure(self):
		pass

	cpdef delete(self):
		if self.buffer_exists:
			gl.DeleteBuffers(1, &self.id)
			self.buffer_exists = False

cdef class MappedBufferObject(BufferObject):
	cdef uint8_t *_ram_buffer
	cdef uint8_t dirty
	cdef GLintptr dirty_min
	cdef GLsizeiptr dirty_max

	def __cinit__(self, GLenum target, GLsizeiptr size, GLenum usage = 0):
		self._ram_buffer = <uint8_t *>malloc(sizeof(uint8_t) * size)
		if self._ram_buffer == NULL:
			raise MemoryError()

		self.dirty = False
		self.dirty_min = 0
		self.dirty_max = 0

	def __dealloc__(self):
		free(self._ram_buffer)

	cpdef set_size_and_data(self, GLsizeiptr size, object data):
		free(self._ram_buffer)
		self._ram_buffer = <uint8_t *>malloc(sizeof(uint8_t) * size)
		if self._ram_buffer == NULL:
			raise MemoryError()

		cdef GLsizeiptr copy_size, tail_size
		copy_size = min(<GLsizeiptr>len(data), size)
		# Hopefully the signed cast is correct here
		tail_size = max(0, <GLintptr>size - <GLintptr>copy_size)
		memcpy(self._ram_buffer, _get_ctypes_data_ptr(data), size)
		memset(self._ram_buffer + copy_size, 0, tail_size)
		self.dirty = False
		self.size = size

	cpdef set_data(self, GLintptr start, GLsizeiptr size, object data):
		memmove(
			self._ram_buffer + start,
			_get_ctypes_data_ptr(data),
			min(<GLintptr>size, <GLintptr>self.size - <GLintptr>start),
		)
		if not self.dirty:
			self.dirty = True
			self.dirty_min = start
			self.dirty_max = start + size
		else:
			self.dirty_min = min(self.dirty_min, start)
			self.dirty_max = max(self.dirty_max, start + size)

	cpdef object get_data(self, GLintptr start, size_t size):
		cdef GLsizeiptr fetched_size = min(size, self.size - start)
		res_buffer = (ctypes.c_ubyte * fetched_size)()
		if fetched_size == 0:
			return res_buffer

		# just stuff the array without its knowledge, what could go wrong
		memcpy(_get_ctypes_data_ptr(res_buffer), self._ram_buffer + start, fetched_size)
		return res_buffer

	cpdef bind(self, GLenum target = 0):
		self.ensure()
		super().bind(target)

	cpdef resize(self, GLsizeiptr new_size):
		cdef uint8_t *new_ptr = <uint8_t *>realloc(self._ram_buffer, new_size)
		if new_ptr == NULL:
			# self._ram_buffer is probably gonna be freed by __dealloc__
			raise MemoryError()

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
