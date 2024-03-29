
#                            NOTICE                             #
# This file was autogenerated by `gl_gen.py`. Do not modify it! #
# (Or do, i'm not your dad.)                                    #
# For permanent changes though, modify the generator script.    #

import ctypes
from pyday_night_funkin.core.graphics.cygl cimport gl

cdef bint _is_initialized = False

cdef gl.GLRegistry _gl_reg

ctypedef void (* SetGLFunc_f)(uintptr_t addressof)

# Completely unsafe hacks that make function addresses available to cython.
# I love and hate C for this.
# https://stackoverflow.com/questions/49635105/ctypes-get-the-actual-address-of-a-c-function

cdef void _register_glGetError(uintptr_t func_ptr):
	_gl_reg.GetError = (<FPTR_GetError *>func_ptr)[0]

cdef void _register_glCreateBuffers(uintptr_t func_ptr):
	_gl_reg.CreateBuffers = (<FPTR_CreateBuffers *>func_ptr)[0]

cdef void _register_glDeleteBuffers(uintptr_t func_ptr):
	_gl_reg.DeleteBuffers = (<FPTR_DeleteBuffers *>func_ptr)[0]

cdef void _register_glBufferData(uintptr_t func_ptr):
	_gl_reg.BufferData = (<FPTR_BufferData *>func_ptr)[0]

cdef void _register_glNamedBufferData(uintptr_t func_ptr):
	_gl_reg.NamedBufferData = (<FPTR_NamedBufferData *>func_ptr)[0]

cdef void _register_glBufferSubData(uintptr_t func_ptr):
	_gl_reg.BufferSubData = (<FPTR_BufferSubData *>func_ptr)[0]

cdef void _register_glNamedBufferSubData(uintptr_t func_ptr):
	_gl_reg.NamedBufferSubData = (<FPTR_NamedBufferSubData *>func_ptr)[0]

cdef void _register_glMapNamedBuffer(uintptr_t func_ptr):
	_gl_reg.MapNamedBuffer = (<FPTR_MapNamedBuffer *>func_ptr)[0]

cdef void _register_glMapNamedBufferRange(uintptr_t func_ptr):
	_gl_reg.MapNamedBufferRange = (<FPTR_MapNamedBufferRange *>func_ptr)[0]

cdef void _register_glUnmapNamedBuffer(uintptr_t func_ptr):
	_gl_reg.UnmapNamedBuffer = (<FPTR_UnmapNamedBuffer *>func_ptr)[0]

cdef void _register_glBindBuffer(uintptr_t func_ptr):
	_gl_reg.BindBuffer = (<FPTR_BindBuffer *>func_ptr)[0]



class OpenGLError(Exception):
	pass


cdef GLRegistry *cygl_get_reg() except NULL:
	if not _is_initialized:
		raise RuntimeError("cygl was not initialized!")
	return &_gl_reg

cdef uint8_t cygl_errcheck() except 1:
	if not _is_initialized:
		raise RuntimeError("cygl was not initialized!")

	cdef GLenum err = _gl_reg.GetError()
	if err == 0:
		return 0

	cdef str err_str = "Unkown error code. Something is seriously off."
	if err == GL_INVALID_ENUM:
		err_str = "Invalid enum value (Oooh what could the cause for this one be?)"
	elif err == GL_INVALID_VALUE:
		err_str = "Invalid value (Most descriptive OpenGL error)"
	elif err == GL_INVALID_OPERATION:
		err_str = "Invalid operation (Happy guessing!)"
	elif err == GL_INVALID_FRAMEBUFFER_OPERATION:
		err_str = "Invalid Framebuffer operation"
	elif err == GL_OUT_OF_MEMORY:
		err_str = "Out of memory"
	raise OpenGLError(err_str)

#########################################################################################
# ! Check the entire codebase for "PNF_OPEN_GL_TYPE_DEFINITIONS" when modifiying this ! #
#########################################################################################
cdef size_t cygl_get_gl_type_size(GLenum type_):
	if type_ in (GL_BYTE, GL_UNSIGNED_BYTE):
		return 1
	elif type_ in (GL_SHORT, GL_UNSIGNED_SHORT):
		return 2
	elif type_ in (GL_INT, GL_UNSIGNED_INT, GL_FLOAT):
		return 4
	elif type_ in (GL_DOUBLE,):
		return 8
	else:
		return 0


NAME_TO_INITIALIZER_DICT = {
	"glGetError": _register_glGetError,
	"glCreateBuffers": _register_glCreateBuffers,
	"glDeleteBuffers": _register_glDeleteBuffers,
	"glBufferData": _register_glBufferData,
	"glNamedBufferData": _register_glNamedBufferData,
	"glBufferSubData": _register_glBufferSubData,
	"glNamedBufferSubData": _register_glNamedBufferSubData,
	"glMapNamedBuffer": _register_glMapNamedBuffer,
	"glMapNamedBufferRange": _register_glMapNamedBufferRange,
	"glUnmapNamedBuffer": _register_glUnmapNamedBuffer,
	"glBindBuffer": _register_glBindBuffer,
}


def initialize(module):
	global _is_initialized
	if _is_initialized:
		return

	cdef set uninitialized = set(NAME_TO_INITIALIZER_DICT)
	cdef uintptr_t address
	for name in NAME_TO_INITIALIZER_DICT:
		address = 0
		try:
			thing = getattr(module, name)
		except AttributeError:
			raise RuntimeError(
				f"GL module did not possess required attribute {name!r}"
			) from None

		if hasattr(thing, "func") and thing.func is None:
			# HACK Not gonna run an isinstance check here
			# This is likely a WGLFunctionProxy.
			# This branch should only run if we are on windows, so importing wglGetProcAddress
			# shooooould succeed.
			# It furthermore shooooould be returning function pointers.
			# Do not bother resolving the proxy, it can go do that on its own.
			# We just need to get the function address.

			from pyglet.gl.lib_wgl import wglGetProcAddress
			name_buf = ctypes.create_string_buffer(thing.name.encode("utf-8"))
			address = <uintptr_t>ctypes.addressof(wglGetProcAddress(name_buf))
			del name_buf
			if address == 0:
				raise RuntimeError(f"wglGetProcAddress returned NULL; {name!r} unavailable")
		else:
			address_haver = thing
			if hasattr(thing, "func"):
				# Likely a WGLFunction (formerly WGLFunctionProxy but with its __class__ attribute
				# replaced like wtf); its func should already be setup and good to go by giving it
				# to addressof.
				address_haver = thing.func

			try:
				address = <uintptr_t>ctypes.addressof(address_haver)
			except TypeError:
				raise TypeError(
					f"ctypes.addressof raised TypeError when trying to register {name!r}, "
					f"type was {address_haver.__class__.__name__!r}"
				) from None

		NAME_TO_INITIALIZER_DICT[name](address)
		uninitialized.remove(name)

	if uninitialized:
		raise RuntimeError(
			f"The cython GL registry was not fully initialized."
			f"First missing value: {next(iter(uninitialized))!r}"
		)

	_is_initialized = True
