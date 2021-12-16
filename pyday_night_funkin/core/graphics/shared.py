"""
Small module containing a bunch of dicts mapping stuff like gl types
and their sizes around.
"""

import ctypes
import re

from pyglet.gl import gl


RE_VERTEX_FORMAT = re.compile("(.*)(\d)(.)(n?)/(static|dynamic|stream)")

C_TYPE_MAP = {
	gl.GL_UNSIGNED_BYTE: ctypes.c_ubyte,
	gl.GL_BYTE: ctypes.c_byte,
	gl.GL_DOUBLE: ctypes.c_double,
	gl.GL_UNSIGNED_INT: ctypes.c_uint,
	gl.GL_INT: ctypes.c_int,
	gl.GL_FLOAT: ctypes.c_float,
	gl.GL_UNSIGNED_SHORT: ctypes.c_ushort,
	gl.GL_SHORT: ctypes.c_short,
}

GL_TYPE_SIZES = {
	gl.GL_UNSIGNED_BYTE: 1,
	gl.GL_BYTE: 1,
	gl.GL_DOUBLE: 8,
	gl.GL_UNSIGNED_INT: 4,
	gl.GL_INT: 4,
	gl.GL_FLOAT: 4,
	gl.GL_UNSIGNED_SHORT: 2,
	gl.GL_SHORT: 2,
}

TYPE_MAP = {
	'B': gl.GL_UNSIGNED_BYTE,
	'b': gl.GL_BYTE,
	'd': gl.GL_DOUBLE,
	'I': gl.GL_UNSIGNED_INT,
	'i': gl.GL_INT,
	'f': gl.GL_FLOAT,
	'S': gl.GL_UNSIGNED_SHORT,
	's': gl.GL_SHORT,
}

USAGE_MAP = {
	"static": gl.GL_STATIC_DRAW,
	"dynamic": gl.GL_DYNAMIC_DRAW,
	"stream": gl.GL_STREAM_DRAW,
}
