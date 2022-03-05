
import ctypes
import typing as t

from pyglet.gl import gl
from pyglet.image import Framebuffer, Texture
from pyglet.math import Mat4, Vec2

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject
from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES
from pyday_night_funkin.core.shaders import ShaderContainer

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram



CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)

_QUAD_VBO_POSITION_SEGMENT_SIZE = GL_TYPE_SIZES[gl.GL_FLOAT] * 12
_QUAD_VBO_POSITION_SEGMENT_START = GL_TYPE_SIZES[gl.GL_FLOAT] * 0
_QUAD_VBO_TEX_COORD_SEGMENT_SIZE = GL_TYPE_SIZES[gl.GL_FLOAT] * 12
_QUAD_VBO_TEX_COORD_SEGMENT_START = GL_TYPE_SIZES[gl.GL_FLOAT] * 12
_QUAD_VBO_SIZE = _QUAD_VBO_POSITION_SEGMENT_SIZE + _QUAD_VBO_TEX_COORD_SEGMENT_SIZE

CAMERA_QUAD_VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec2 position;
layout (location = 1) in vec2 tex_coords;

uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
} camera;

out vec2 texture_coords;

void main() {
	gl_Position = 
		window.projection *
		window.view *
		vec4(position, 0.0, 1.0);

	texture_coords = tex_coords;
}
"""

CAMERA_QUAD_FRAGMENT_SHADER = """
#version 330 core
in vec2 texture_coords;

out vec4 final_color;

uniform sampler2D camera_texture;

void main() {
	final_color = texture(camera_texture, texture_coords);
}
"""


class Camera:
	"""
	Camera class to provide a UBO (which needs to be reflected in the
	shader code of shaders that want to use it) that transforms
	drawables as if they were viewed translated/zoomed with a camera.
	Concepts largely stolen from
	https://github.com/HaxeFlixel/flixel/blob/dev/flixel/FlxCamera.hx
	"""

	_dummy: t.Optional["Camera"] = None
	_shader_container = ShaderContainer(
		CAMERA_QUAD_VERTEX_SHADER, CAMERA_QUAD_FRAGMENT_SHADER
	)

	def __init__(self, x: int, y: int, w: int, h: int):
		self._x = x
		"""Absolute x position of the camera's display quad."""
		self._y = y
		"""Absolute y position of the camera's display quad."""

		self._width = w
		"""True pixel width of the camera's display quad."""
		self._height = h
		"""True pixel height of the camera's display quad."""

		self._rotation = 0
		"""Rotation of the camera's display quad."""

		self._view_width = self._width
		"""
		Width of the world area displayed by the camera.
		Affected by zoom.
		"""
		self._view_width = self._height
		"""
		Height of the world area displayed by the camera.
		Affected by zoom.
		"""

		self._zoom = 1.0

		self._follow_target = None
		self._follow_lerp = 1.0

		self._effect_shaders: t.List["ShaderProgram"] = []
		"""
		A list of shaders that will be sequentially applied to this
		camera's display quad.
		"""

		self.framebuffer = Framebuffer()
		self.texture = Texture.create(w, h)
		self.framebuffer.attach_texture(self.texture)

		self.program = self._shader_container.get_program()
		self.ubo = self._shader_container.get_camera_ubo()

		self.vao = gl.GLuint()
		"""
		VAO that needs to be bound to properly render the camera's
		display quad.
		"""

		self.vbo = BufferObject(gl.GL_ARRAY_BUFFER, _QUAD_VBO_SIZE, gl.GL_DYNAMIC_DRAW)
		"""
		VBO containing the vertices to properly render the camera's
		display quad.
		"""

		# self.projection_matrix = None
		# """
		# Projection matrix that should be bound to window.projection
		# before rendering with this camera.
		# """

		# Below is largely stolen from
		# https://learnopengl.com/Advanced-OpenGL/Framebuffers

		# These should be totally wrong, but it works. Don't ask.
		tex_coords = (ctypes.c_float * 12)(
			 0.,  0.,
			 1.,  1.,
			 1.,  0.,
			 0.,  0.,
			 1.,  1.,
			 0.,  1.,
		)
		self.vbo.set_data(
			_QUAD_VBO_TEX_COORD_SEGMENT_START,
			_QUAD_VBO_TEX_COORD_SEGMENT_SIZE,
			tex_coords,
		)

		gl.glCreateVertexArrays(1, ctypes.byref(self.vao))
		gl.glBindVertexArray(self.vao)
		self.vbo.bind()
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(
			0,
			2,
			gl.GL_FLOAT,
			gl.GL_FALSE,
			2 * GL_TYPE_SIZES[gl.GL_FLOAT],
			_QUAD_VBO_POSITION_SEGMENT_START,
		)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(
			1,
			2,
			gl.GL_FLOAT,
			gl.GL_FALSE,
			2 * GL_TYPE_SIZES[gl.GL_FLOAT],
			_QUAD_VBO_TEX_COORD_SEGMENT_START,
		)
		gl.glBindVertexArray(0)

		self._update_ubo()
		self._update_vbo()
		# self._update_proj_mat()

	@classmethod
	def get_dummy(cls) -> "Camera":
		"""
		Returns the global dummy camera.
		"""
		if cls._dummy is None:
			cls._dummy = cls(0, 0, GAME_WIDTH, GAME_HEIGHT)
		return cls._dummy

	def _update_ubo(self) -> None:
		with self.ubo as ubo:
			ubo.zoom = self._zoom
			ubo.position[:] = (self._x, self._y)
			ubo.GAME_DIMENSIONS[:] = (GAME_WIDTH, GAME_HEIGHT)

	def _update_vbo(self) -> None:
		x1 = self._x
		y1 = self._y + self._height
		x2 = self._x + self._width
		y2 = self._y
		v = [
			(x1, y1), #0
			(x2, y1), #1
			(x2, y2), #2
			(x1, y2), #3
		]
		# Not going through the trouble of indexing (yet)
		data = (ctypes.c_float * 12)(*v[0], *v[2], *v[1], *v[0], *v[2], *v[3])
		self.vbo.set_data(0, _QUAD_VBO_POSITION_SEGMENT_SIZE, data)

	# def _update_proj_mat(self) -> None:
	# 	self.projection_matrix = Mat4.orthogonal_projection(
	# 		0, self._width, self._height, 0, -1, 1
	# 	)

	def update(self, dt: float) -> None:
		if self._follow_target is not None:
			self._update_follow_target(dt)

	def look_at(self, where: Vec2) -> None:
		"""
		Immediatedly sets the camera's target position to look at the
		given point.
		"""
		# This may not respect zoom. Or, it may, and I am completely
		# forgetting something.
		self._x = where[0] - CENTER_X # (self._width / 2)
		self._y = where[1] - CENTER_Y # (self._height / 2)
		self._update_ubo()

	def set_follow_target(self, tgt: t.Optional[Vec2], lerp: float = 1.0):
		self._follow_target = tgt
		self._follow_lerp = lerp

	def _update_follow_target(self, dt: float) -> None:
		# There used to be a deadzone in the FlxCamera, but all uses
		# within the fnf source (follow target is a point) have its
		# width and height set to 0, so the deadzone is effectively
		# reduced to a point. Take advantage of that and reduce it
		# to the halved display width here.

		tgt_x = self._follow_target[0] - CENTER_X # (self._width / 2)
		tgt_y = self._follow_target[1] - CENTER_Y # (self._height / 2)

		self._x += (tgt_x - self._x) * self._follow_lerp
		self._y += (tgt_y - self._y) * self._follow_lerp
		self._update_ubo()

	@property
	def x(self) -> int:
		return self._x

	@x.setter
	def x(self, new_x: int) -> None:
		self._x = new_x
		self._update_ubo()

	@property
	def y(self) -> int:
		return self._y

	@y.setter
	def y(self, new_y: int) -> None:
		self._y = new_y
		self._update_ubo()

	@property
	def zoom(self) -> float:
		return self._zoom

	@zoom.setter
	def zoom(self, new_zoom: float) -> None:
		self._zoom = new_zoom
		self._update_ubo()

	def delete(self) -> None:
		self._framebuffer.delete()
		self._framebuffer = None
		self.texture = None
		self.vbo.delete()
		gl.glDeleteVertexArrays(1, ctypes.byref(self.vao))
