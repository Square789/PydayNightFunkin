"""
This stuff is more or less a dumbed down copy of the vertexbuffers
found in `pyglet.graphics.vertexbuffer`.
"""


import ctypes
import typing as t

from pyglet.gl import gl


class BufferObject:
	"""
	Python class wrapping an OpenGL buffer.
	"""

	def __init__(self, target: int, size: int, usage: int = gl.GL_DYNAMIC_READ) -> None:
		self.id = gl.GLuint()
		self.usage = usage
		self.target = target
		self.size = size

		gl.glCreateBuffers(1, self.id)
		gl.glNamedBufferData(self.id, size, None, usage)

	def set_size_and_data(self, size: int, data: ctypes.Array) -> None:
		"""
		Resizes the buffer to accomodate the new data of the given
		`size`.
		"""
		gl.glNamedBufferData(self.id, size, data, self.usage)
		self.size = size

	def set_data(self, start: int, size: int, data: ctypes.Array) -> None:
		"""
		Sets the next `size` bytes starting from `start` to `data`.
		`data` must be of the same length as `size` and the size may
		not exceed the buffer's size.
		"""
		gl.glNamedBufferSubData(self.id, start, size, data)

	def get_data(self, start: int, size: int) -> ctypes.Array:
		"""
		Retrieves the next `size` bytes from `start`.
		May be truncated if `size` exceeds the buffer's size.
		"""
		fetched_size = min(size, self.size - start)
		res = (ctypes.c_ubyte * fetched_size)()
		if fetched_size == 0:
			return res

		data = gl.glMapNamedBufferRange(
			self.id,
			start,
			fetched_size,
			gl.GL_MAP_READ_BIT,
		)
		ctypes.memmove(res, data, fetched_size)
		gl.glUnmapNamedBuffer(self.id)
		return res

	def bind(self, target: t.Optional[int] = None) -> None:
		"""
		Binds the buffer by binding it to the specified target or its
		standard `__init__`-given target.
		"""
		gl.glBindBuffer(self.target if target is None else target, self.id)

	def resize(self, new_size: int) -> None:
		"""
		Resizes the buffer to take `new_size` bytes. Will truncate or
		zero-fill existing data, depending on whether the buffer grew
		or shrunk.
		"""
		gl.glNamedBufferData(
			self.id,
			new_size,
			self.get_data(0, min(new_size, self.size)),
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


class MappedBufferObject(BufferObject):
	def __init__(self, target: int, size: int, usage: int = gl.GL_DYNAMIC_READ) -> None:
		super().__init__(target, size, usage)

		self._ram_buffer = (ctypes.c_ubyte * size)()
		self._dirty = False
		self._dirty_min = 0
		self._dirty_max = 0

	def set_size_and_data(self, size: int, data: ctypes.Array) -> None:
		"""
		Resizes the buffer to accomodate the new data of the given
		`size`. Does not copy `data`, so be sure to not modify it
		after passing it to this function.
		"""
		self._ram_buffer = data
		gl.glNamedBufferData(self.id, size, data, self.usage)
		self._dirty = False
		self.size = size

	def set_data(self, start: int, size: int, data: ctypes.Array) -> None:
		ctypes.memmove(
			ctypes.addressof(self._ram_buffer) + start,
			ctypes.byref(data),
			min(size, self.size - start), # whichever is smaller: given array size or remaining
		)
		if not self._dirty:
			self._dirty = True
			self._dirty_min = start
			self._dirty_max = start + size
		else:
			self._dirty_min = min(self._dirty_min, start)
			self._dirty_max = max(self._dirty_max, start + size)

	def get_data(self, start: int, size: int) -> ctypes.Array:
		r = self._ram_buffer[start : start+size]
		return (ctypes.c_ubyte * len(r))(*r)

	def bind(self, target: t.Optional[int] = None) -> None:
		"""
		Binds the MappableBufferObject by uploading possibly pending
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
