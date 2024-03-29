
import ctypes
import typing as t

Numeric = t.Union[int, float]

Ctype = t.Type[t.Union[
	ctypes.c_bool, ctypes.c_byte, ctypes.c_char, ctypes.c_char_p, ctypes.c_double,
	ctypes.c_float, ctypes.c_int, ctypes.c_int8, ctypes.c_int16, ctypes.c_int32,
	ctypes.c_int64, ctypes.c_long, ctypes.c_longdouble, ctypes.c_longlong, ctypes.c_short,
	ctypes.c_size_t, ctypes.c_ssize_t, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_uint8,
	ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_ulong, ctypes.c_ulonglong,
	ctypes.c_ushort, ctypes.c_void_p, ctypes.c_wchar, ctypes.c_wchar_p
]]
