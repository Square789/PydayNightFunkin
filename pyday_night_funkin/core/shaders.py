
from pyglet.gl import gl
from pyglet.graphics.shader import Shader, ShaderProgram, UniformBufferObject


class ShaderContainer:
	"""
	Class to hold multiple shaders and compile them to a full
	program only when requested for the first time.
	Has some special support for cameras and requirements to the
	shaders:
	- A `WindowBlock` uniform block must be contained which will be
	  sourced from uniform buffer index 0.
	- A `CameraAttrs` uniform block must be contained which will be
	  sourced from uniform buffer index 1.
	"""

	def __init__(self, vertex_src: str, fragment_src: str) -> None:
		self._prog = None
		self.vertex_src = vertex_src
		self.fragment_src = fragment_src

	def get_program(self) -> ShaderProgram:
		"""
		If needed, compiles, and returns the program.
		"""
		if self._prog is None:
			self._compile()
		return self._prog

	def get_camera_ubo(self) -> UniformBufferObject:
		"""
		Returns a new Uniform Buffer Object for the shader program's
		`CameraAttrs` uniform block, which will bind at the binding
		index the program expects.
		"""
		return self.get_program().uniform_blocks["CameraAttrs"].create_ubo(1)

	def _compile(self) -> None:
		"""
		Compiles and sets up the program.
		"""
		vertex_shader = Shader(self.vertex_src, "vertex")
		fragment_shader = Shader(self.fragment_src, "fragment")
		self._prog = ShaderProgram(vertex_shader, fragment_shader)
		# Window block binds itself to 0 and is a pain to control outside of
		# the actual window class, so just source it from binding point 0
		gl.glUniformBlockBinding(self._prog.id, self._prog.uniform_blocks["WindowBlock"].index, 0)
		# Source camera attributes from binding point 1
		gl.glUniformBlockBinding(self._prog.id, self._prog.uniform_blocks["CameraAttrs"].index, 1)
