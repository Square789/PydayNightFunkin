"""
Small module containing a bunch of dicts mapping stuff like gl types
and their sizes around.
"""

import ctypes
import re
import typing as t

from pyglet.gl import gl

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.types import Ctype


RE_VERTEX_FORMAT = re.compile("(.*)(\d)(.)(n?)(?:/(static|dynamic|stream))?")

#########################################################################################
# ! Check the entire codebase for "PNF_OPEN_GL_TYPE_DEFINITIONS" when modifiying this ! #
#########################################################################################

GL_TO_C_TYPE_MAP: t.Dict[int, "Ctype"] = {
	gl.GL_BYTE: ctypes.c_byte,
	gl.GL_UNSIGNED_BYTE: ctypes.c_ubyte,
	gl.GL_SHORT: ctypes.c_short,
	gl.GL_UNSIGNED_SHORT: ctypes.c_ushort,
	gl.GL_INT: ctypes.c_int,
	gl.GL_UNSIGNED_INT: ctypes.c_uint,
	gl.GL_FLOAT: ctypes.c_float,
	gl.GL_DOUBLE: ctypes.c_double,
}

GL_TYPE_SIZES = {
	gl.GL_BYTE: 1,
	gl.GL_UNSIGNED_BYTE: 1,
	gl.GL_SHORT: 2,
	gl.GL_UNSIGNED_SHORT: 2,
	gl.GL_INT: 4,
	gl.GL_UNSIGNED_INT: 4,
	gl.GL_FLOAT: 4,
	gl.GL_DOUBLE: 8,
}

# sanity check i guess
for gl_type, size in GL_TYPE_SIZES.items():
	ct = GL_TO_C_TYPE_MAP[gl_type]
	if ctypes.sizeof(ct) != size:
		raise RuntimeError(
			f"Size discrepancy for the ctype equivalent {ct} of gl type {gl_type}, "
			f"was {ctypes.sizeof(ct)}, should have been {size}!"
		)


TYPECHAR_TO_GL_TYPE_MAP = {
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
