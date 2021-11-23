
import typing as t

from pyglet.gl import gl
from pyglet.graphics.shader import Shader, ShaderProgram, UniformBufferObject


_PNF_SPRITE_VERTEX_SHADER_SOURCE = """
#version 330

in vec2 anim_offset;
in vec2 frame_offset;
in vec2 translate;
in vec4 colors;
in vec3 tex_coords;
in vec2 scale;
in vec2 position;
in vec2 scroll_factor;
in float rotation;

out vec4 vertex_colors;
out vec3 texture_coords;

uniform WindowBlock {{
	mat4 projection;
	mat4 view;
}} window;

// Not really sure about having GAME_DIMENSIONS here
// since it's by all means a constant

layout (std140) uniform CameraAttrs {{
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
}} camera;


mat4 m_trans_scale = mat4(1.0);
mat4 m_rotation = mat4(1.0);
mat4 m_camera_trans_scale = mat4(1.0);
mat4 m_camera_pre_trans = mat4(1.0);


void main() {{
	m_trans_scale[3][0] = translate.x + anim_offset.x + frame_offset.x * scale.x;
	m_trans_scale[3][1] = translate.y + anim_offset.y + frame_offset.y * scale.y;
	m_trans_scale[0][0] = scale.x;
	m_trans_scale[1][1] = scale.y;
	m_rotation[0][0] =  cos(-radians(rotation));
	m_rotation[0][1] =  sin(-radians(rotation));
	m_rotation[1][0] = -sin(-radians(rotation));
	m_rotation[1][1] =  cos(-radians(rotation));
	// Camera transform and zoom scale
	m_camera_trans_scale[3][0] = (camera.zoom * scroll_factor.x * -camera.position.x) + \\
		(camera.GAME_DIMENSIONS.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * scroll_factor.y * -camera.position.y) + \\
		(camera.GAME_DIMENSIONS.y / 2);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;
	// Camera pre-scale-transform
	m_camera_pre_trans[3][0] = -camera.GAME_DIMENSIONS.x / 2;
	m_camera_pre_trans[3][1] = -camera.GAME_DIMENSIONS.y / 2;

	gl_Position = \\
		window.projection * \\
		window.view * \\
		m_camera_trans_scale * \\
		m_camera_pre_trans * \\
		m_trans_scale * \\
		m_rotation * \\
		vec4(position, 0, 1) \\
	;

	vertex_colors = colors;
	texture_coords = tex_coords;
}}
"""

_PNF_SPRITE_FRAGMENT_SHADER_SOURCE = """
#version 150 core

in vec4 vertex_colors;
in vec3 texture_coords;

out vec4 final_colors;

uniform sampler2D sprite_texture;


void main() {{
	if (vertex_colors.a < {alpha_limit}) {{
		discard;
	}}

	final_colors = {color_behavior};
}}
"""

class PNFSpriteVertexShader():
	src = _PNF_SPRITE_VERTEX_SHADER_SOURCE

	@classmethod
	def generate(cls) -> str:
		return cls.src.format()


class PNFSpriteFragmentShader():
	src = _PNF_SPRITE_FRAGMENT_SHADER_SOURCE 

	class COLOR:
		BLEND = "texture(sprite_texture, texture_coords.xy) * vertex_colors"
		SET =   "vec4(vertex_colors.rgb, texture(sprite_texture, texture_coords.xy).a)"

	@classmethod
	def generate(
		cls,
		alpha_limit: float = 0.01,
		color_behavior: str = COLOR.BLEND,
	) -> str:
		return cls.src.format(
			alpha_limit=alpha_limit,
			color_behavior=color_behavior,
		)


class ShaderContainer():
	"""
	Class to hold multiple shaders and compile them to a full
	program only when requested for the first time.
	"""
	def __init__(self, vertex_src: str, fragment_src: str) -> None:
		self._prog = None
		self.vertex_src = vertex_src
		self.fragment_src = fragment_src

	def get_program(self) -> ShaderProgram:
		"""
		Returns the program associated with PNFSprites.
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
