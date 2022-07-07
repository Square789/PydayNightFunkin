
from pathlib import Path
import sys

HYPER_UNSAFE = "--hyper-unsafe" in sys.argv

#########################################################################################
# ! Check the entire codebase for "PNF_OPEN_GL_TYPE_DEFINITIONS" when modifiying this ! #
#########################################################################################
TYPES = {
	("GL_BYTE",           "byte",           1, "int8_t",   "int"),
	("GL_UNSIGNED_BYTE",  "unsigned_byte",  1, "uint8_t",  "int"),
	("GL_SHORT",          "short",          2, "int16_t",  "int"),
	("GL_UNSIGNED_SHORT", "unsigned_short", 2, "uint16_t", "int"),
	("GL_INT",            "int",            4, "int32_t",  "int"),
	("GL_UNSIGNED_INT",   "unsigned_int",   4, "uint32_t", "int"),
	("GL_FLOAT",          "float",          4, "float",    "float"),
	("GL_DOUBLE",         "double",         8, "double",   "float"),
}

HEADER = """
#                                 NOTICE                                 #
# This file was autogenerated by `vertexbuffer_gen_pyobj_extractors.py`. #
# Do not modify it! (Or do, i'm not your dad.)                           #
# For permanent changes though, modify the generator script.             #

ctypedef uint8_t (* FPTR_pyobj_extractor)(size_t size, void *target, object data_iterable) except 1
"""

EXTRACTOR_SKELETON_SAFETY_BLOCK = """
		if not isinstance(it, (int, float)):
			raise TypeError(f"Bad python type {{type(it)!r}} for supplied buffer data.")
		if i >= size:
			break
"""

EXTRACTOR_SKELETON = """
cdef uint8_t extract_{{c_type_name}}s(size_t size, void *target, object data_iterable) except 1:
	cdef {{c_typedef}} *cast_target = <{{c_typedef}} *>target
	cdef size_t i = 0
	for i, it in enumerate(data_iterable):{}
		cast_target[i] = <{{c_typedef}}>it
	return 0
""".format("" if HYPER_UNSAFE else EXTRACTOR_SKELETON_SAFETY_BLOCK)


GET_EXTRACTOR_TEMPLATE = """
cdef inline FPTR_pyobj_extractor get_pyobj_extractor_function(GLenum gl_type):
{}
	return NULL
"""

def main():
	_path = Path("PydayNightFunkin/pyday_night_funkin/core/graphics")
	generator_path = Path.cwd()
	while _path.parts:
		head, *tail = _path.parts
		if generator_path.name == head:
			generator_path /= Path(*tail)
			break
		_path = Path(*tail)
	else:
		return 1

	funcdefs = []

	for _, func_name, size, c_typedef, python_equiv in TYPES:
		func = EXTRACTOR_SKELETON.format(
			c_type_name = func_name,
			c_typedef = c_typedef,
			expected_py_type = python_equiv,
			cast_safety = '' if HYPER_UNSAFE else '?',
		)
		funcdefs.append(func)

	extractor_switch = ""
	for i, (gl_type_name, c_name, _, _, _) in enumerate(TYPES):
		word = "if" if i == 0 else "elif"
		extractor_switch += f"\t{word} gl_type == {gl_type_name}:\n"
		extractor_switch += f"\t\treturn extract_{c_name}s\n"

	extractor_getter = GET_EXTRACTOR_TEMPLATE.format(extractor_switch)

	with (
		generator_path / "vertexbuffer_pyobj_extractors.pxi"
	).open("w", encoding = "utf-8") as f:
		f.write(HEADER + "".join(funcdefs) + extractor_getter)


if __name__ == "__main__":
	sys.exit(main())
