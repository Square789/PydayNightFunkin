
import ctypes
import typing as t

if t.TYPE_CHECKING:
	from pyglet.math import Vec2, Vec3, Vec4


Numeric = t.Union[int, float]

Ctype = t.Type[t.Union[
	ctypes.c_bool, ctypes.c_byte, ctypes.c_char, ctypes.c_char_p, ctypes.c_double,
	ctypes.c_float, ctypes.c_int, ctypes.c_int8, ctypes.c_int16, ctypes.c_int32,
	ctypes.c_int64, ctypes.c_long, ctypes.c_longdouble, ctypes.c_longlong, ctypes.c_short,
	ctypes.c_size_t, ctypes.c_ssize_t, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_uint8,
	ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_ulong, ctypes.c_ulonglong,
	ctypes.c_ushort, ctypes.c_void_p, ctypes.c_wchar, ctypes.c_wchar_p
]]


CoordIndexable = t.Union[t.Sequence[float], "Vec2", "Vec3", "Vec4"]
"""
A cheap type intended to mark acceptance of classes that can be
indexed from 0 to 3-ish to get floats from them.

Realistically, this applies to tuples or other sequences of two
floats and ``pyglet.math.Vec2`` and its related vector classes.

Makes it easier to either pass in cheap tuples or Vec2 calculation
results into various user-facing objects.
"""
