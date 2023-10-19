
#                            NOTICE                   #
# This file was autogenerated by `codegen/gl_gen.py`. #
# Do not modify it! (Or do, i'm not your dad.)        #
# For permanent changes though, modify `gl_gen.py`.   #

from libc.stdint cimport *


ctypedef unsigned int GLenum
ctypedef unsigned char GLboolean
ctypedef void GLvoid
ctypedef int GLint
ctypedef unsigned int GLuint
ctypedef int GLsizei
ctypedef unsigned long int GLsizeiptr
ctypedef long int GLintptr
ctypedef double GLdouble
ctypedef char GLchar
ctypedef unsigned int GLbitfield

ctypedef void (* FPTR_BindBuffer)(GLenum target, GLuint buffer)
ctypedef void (* FPTR_BufferData)(GLenum target, GLsizeiptr size, const void *data, GLenum usage)
ctypedef void (* FPTR_BufferSubData)(GLenum target, GLintptr offset, GLsizeiptr size, const void *data)
ctypedef void (* FPTR_CreateBuffers)(GLsizei n, GLuint *buffers)
ctypedef void (* FPTR_DeleteBuffers)(GLsizei n, const GLuint *buffers)
ctypedef GLenum (* FPTR_GetError)()
ctypedef void *(* FPTR_MapNamedBuffer)(GLuint buffer, GLenum access)
ctypedef void *(* FPTR_MapNamedBufferRange)(GLuint buffer, GLintptr offset, GLsizeiptr length, GLbitfield access)
ctypedef void (* FPTR_NamedBufferData)(GLuint buffer, GLsizeiptr size, const void *data, GLenum usage)
ctypedef void (* FPTR_NamedBufferSubData)(GLuint buffer, GLintptr offset, GLsizeiptr size, const void *data)
ctypedef GLboolean (* FPTR_UnmapNamedBuffer)(GLuint buffer)


cdef extern from *:
	"""
	#define GL_MAP_READ_BIT 0x0001
	#define GL_MAP_WRITE_BIT 0x0002
	#define GL_INVALID_ENUM 0x0500
	#define GL_INVALID_VALUE 0x0501
	#define GL_INVALID_OPERATION 0x0502
	#define GL_OUT_OF_MEMORY 0x0505
	#define GL_INVALID_FRAMEBUFFER_OPERATION 0x0506
	#define GL_BYTE 0x1400
	#define GL_UNSIGNED_BYTE 0x1401
	#define GL_SHORT 0x1402
	#define GL_UNSIGNED_SHORT 0x1403
	#define GL_INT 0x1404
	#define GL_UNSIGNED_INT 0x1405
	#define GL_FLOAT 0x1406
	#define GL_DOUBLE 0x140A
	#define GL_READ_ONLY 0x88B8
	#define GL_DYNAMIC_READ 0x88E9
	"""
	const GLenum GL_MAP_READ_BIT
	const GLenum GL_MAP_WRITE_BIT
	const GLenum GL_INVALID_ENUM
	const GLenum GL_INVALID_VALUE
	const GLenum GL_INVALID_OPERATION
	const GLenum GL_OUT_OF_MEMORY
	const GLenum GL_INVALID_FRAMEBUFFER_OPERATION
	const GLenum GL_BYTE
	const GLenum GL_UNSIGNED_BYTE
	const GLenum GL_SHORT
	const GLenum GL_UNSIGNED_SHORT
	const GLenum GL_INT
	const GLenum GL_UNSIGNED_INT
	const GLenum GL_FLOAT
	const GLenum GL_DOUBLE
	const GLenum GL_READ_ONLY
	const GLenum GL_DYNAMIC_READ


ctypedef struct GLRegistry:
	FPTR_BindBuffer BindBuffer
	FPTR_BufferData BufferData
	FPTR_BufferSubData BufferSubData
	FPTR_CreateBuffers CreateBuffers
	FPTR_DeleteBuffers DeleteBuffers
	FPTR_GetError GetError
	FPTR_MapNamedBuffer MapNamedBuffer
	FPTR_MapNamedBufferRange MapNamedBufferRange
	FPTR_NamedBufferData NamedBufferData
	FPTR_NamedBufferSubData NamedBufferSubData
	FPTR_UnmapNamedBuffer UnmapNamedBuffer


cdef GLRegistry *cygl_get_reg() except NULL
cdef uint8_t cygl_errcheck() except 1
cdef size_t cygl_get_gl_type_size(GLenum type_)
