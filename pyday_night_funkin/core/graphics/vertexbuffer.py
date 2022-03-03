"""
This stuff is more or less a dumbed down copy of the vertexbuffers
found in `pyglet.graphics.vertexbuffer`. Experimental and not finished.
"""


import ctypes
import typing as t

from pyglet.gl import gl

# TODO Write documentation if this turns out to be worth keeping

class BufferObject:
	"""
	Python class wrapping an OpenGL buffer.
	"""

	def __init__(self, target: int, size: int, usage: int = gl.GL_DYNAMIC_READ) -> None:
		self.id = gl.GLuint()
		self.usage = usage
		self.target = target
		self.size = size
		self._deleted = False

		gl.glCreateBuffers(1, self.id)
		gl.glNamedBufferData(self.id, size, None, usage)

	def set_size_and_data(self, size: int, data: int) -> None:
		gl.glNamedBufferData(self.id, size, data, self.usage)
		self.size = size

	def set_data(self, start: int, size: int, data: ctypes.Array) -> None:
		gl.glNamedBufferSubData(self.id, start, size, data)

	def get_data(self, start: int, size: int) -> ctypes.Array:
		res = (ctypes.c_ubyte * size)()
		data = gl.glMapNamedBuffer(self.id, gl.GL_READ_ONLY)
		ctypes.memmove(res, data + start, size)
		gl.glUnmapNamedBuffer(self.id)
		return res

	def bind(self, target: t.Optional[int] = None) -> None:
		gl.glBindBuffer(self.target if target is None else target, self.id)

	def resize(self, new_size: int) -> None:
		gl.glNamedBufferData(
			self.id,
			new_size,
			self.get_data(0, min(new_size, self.size)),
			self.usage,
		)
		self.size = new_size

	def delete(self) -> None:
		if self._deleted:
			return

		gl.glDeleteBuffers(1, self.id)
		self._deleted = True

	def __del__(self) -> None:
		self.delete()


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
		"""
		Sets the next `size` bytes starting from `start` to `data`.
		`data` must be of the same length as `size` and the size may
		not exceed the buffer's size.
		"""
		# bytes required to handle any type that isn't c_[u]byte
		self._ram_buffer[start : start+size] = bytes(data)
		if not self._dirty:
			self._dirty = True
			self._dirty_min = start
			self._dirty_max = start + size
		else:
			self._dirty_min = min(self._dirty_min, start)
			self._dirty_max = max(self._dirty_max, start + size)

	def get_data(self, start: int, size: int) -> ctypes.Array:
		"""
		Retrieves the next `size` bytes from `start`.
		May be truncated if `size` exceeds the buffer's size.
		"""
		return self._ram_buffer[start : start+size]

	def bind(self, target: t.Optional[int] = None) -> None:
		"""
		Binds the MappableBufferObject by uploading possibly pending
		data and then binding it to the specified target or its
		standard `__init__`-given target.
		"""
		self.ensure()
		super().bind(target)

	def resize(self, new_size: int) -> None:
		"""
		Resizes the MappableBufferObject to take `new_size` bytes.
		Will truncate or zero-fill existing data, depending on whether
		the buffer grew or shrunk.
		"""
		new = (ctypes.c_ubyte * new_size)()
		ctypes.memmove(new, self._ram_buffer, min(new_size, self.size))
		self._ram_buffer = new
		gl.glNamedBufferData(self.id, new_size, None, self.usage)
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
