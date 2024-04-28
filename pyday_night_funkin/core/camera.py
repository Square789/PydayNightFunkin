
import ctypes
import typing as t

from pyglet.gl import gl
from pyglet.image import Framebuffer, Texture

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject
from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES
from pyday_night_funkin.core.shaders import ShaderContainer
from pyday_night_funkin.core.types import CoordIndexable

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram


_QUAD_VBO_POSITION_SEGMENT_SIZE = GL_TYPE_SIZES[gl.GL_FLOAT] * 2 * 6
_QUAD_VBO_POSITION_SEGMENT_START = 0
_QUAD_VBO_TEX_COORD_SEGMENT_SIZE = GL_TYPE_SIZES[gl.GL_FLOAT] * 2 * 6
_QUAD_VBO_TEX_COORD_SEGMENT_START = (
	_QUAD_VBO_POSITION_SEGMENT_START +
	_QUAD_VBO_POSITION_SEGMENT_SIZE
)
_QUAD_VBO_FILL_COLOR_SEGMENT_SIZE = GL_TYPE_SIZES[gl.GL_UNSIGNED_BYTE] * 4 * 6
_QUAD_VBO_FILL_COLOR_SEGMENT_START = (
	_QUAD_VBO_TEX_COORD_SEGMENT_START +
	_QUAD_VBO_TEX_COORD_SEGMENT_SIZE
)
_QUAD_VBO_SIZE = (
	_QUAD_VBO_POSITION_SEGMENT_SIZE +
	_QUAD_VBO_TEX_COORD_SEGMENT_SIZE +
	_QUAD_VBO_FILL_COLOR_SEGMENT_SIZE
)

CAMERA_QUAD_VERTEX_SHADER = """
#version 450
layout (location = 0) in vec2 position;
layout (location = 1) in vec2 in_texture_coords;
layout (location = 2) in vec4 in_fill_color;

out vec2 texture_coords;
out vec4 fill_color;

uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  dimensions;
	vec2  focus_center;
} camera;

void main() {
	gl_Position =
		window.projection *
		window.view *
		vec4(position, 0.0, 1.0);

	texture_coords = in_texture_coords;
	fill_color = in_fill_color;
}
"""

CAMERA_QUAD_FRAGMENT_SHADER = f"""
#version 450
in vec2 texture_coords;
in vec4 fill_color;

out vec4 final_color;

uniform sampler2D camera_texture;

void main() {{
	vec4 out_color = texture(camera_texture, texture_coords);

	// float fill_alpha = fill_color.a;
	// // This is your standard SRC_ALPHA, ONE_MINUS_SRC_ALPHA, ONE, ONE_MINUS_SRC_ALPHA
	// // blending calculation.
	// final_color = vec4(
	// 	fill_color.r * fill_alpha + out_color.r * (1.0 - fill_alpha),
	// 	fill_color.g * fill_alpha + out_color.g * (1.0 - fill_alpha),
	// 	fill_color.b * fill_alpha + out_color.b * (1.0 - fill_alpha),
	// 	fill_color.a * 1.0        + out_color.a * (1.0 - fill_alpha)
	// );
	final_color = out_color;
}}
"""


class SimpleCamera:
	"""
	Camera class to provide a UBO (which needs to be reflected in the
	shader code of shaders that want to use it) that transforms
	drawables as if they were viewed translated/zoomed with a camera.
	"""

	_shader_container = ShaderContainer(
		CAMERA_QUAD_VERTEX_SHADER, CAMERA_QUAD_FRAGMENT_SHADER
	)

	def __init__(self, w: int, h: int):
		self._x = 0
		"""
		Top-left-most world x coordinate the camera would be showing at
		zoom 1.0.
		"""
		self._y = 0
		"""
		Top-left-most world y coordinate the camera would be showing at
		zoom 1.0.
		"""

		self._width = w
		self._height = h

		self._focus_center_x = self._width * 0.5
		self._focus_center_y = self._height * 0.5

		self._zoom = 1.0

		self._follow_target = None
		self._follow_lerp = 1.0

		self.ubo = self._shader_container.get_camera_ubo()
		self._ubo_needs_update = False
		self._update_ubo()

	def _update_ubo(self) -> None:
		with self.ubo as ubo:
			ubo.zoom = self._zoom
			ubo.position[:] = (self._x, self._y)
			ubo.dimensions[:] = (self._width, self._height)
			ubo.focus_center[:] = (self._focus_center_x, self._focus_center_y)

	def maybe_update_ubo(self) -> None:
		"""If needed, uploads new data to the camera's UBO."""
		if self._ubo_needs_update:
			self._update_ubo()
			self._ubo_needs_update = False

	def update(self, dt: float) -> None:
		if self._follow_target is not None:
			self._update_follow_target(dt)

		self.maybe_update_ubo()

	def look_at(self, where: CoordIndexable) -> None:
		"""
		Immediatedly sets the camera's target position to look at the
		given point.
		"""
		self._x = where[0] - (self._width / 2)
		self._y = where[1] - (self._height / 2)
		self._ubo_needs_update = True

	def set_follow_target(self, tgt: t.Optional[CoordIndexable], lerp: float = 1.0) -> None:
		self._follow_target = tgt
		self._follow_lerp = lerp

	def _update_follow_target(self, dt: float) -> None:
		# There used to be a deadzone in the FlxCamera, but all uses
		# within the fnf source (follow target is a point) have its
		# width and height set to 0, so the deadzone is effectively
		# reduced to a point. Take advantage of that and reduce it
		# to the halved display width here.

		tgt_x = self._follow_target[0] - (self._width / 2)
		tgt_y = self._follow_target[1] - (self._height / 2)

		self._x += (tgt_x - self._x) * self._follow_lerp
		self._y += (tgt_y - self._y) * self._follow_lerp
		self._ubo_needs_update = True

	@property
	def focus_center(self) -> t.Tuple[float, float]:
		"""
		The location the camera considers its center. If the camera looks
		at this point (meaning its position is actually half its width and
		height to the top-left), the scroll factor of all drawables drawn
		through it are irrelevant.

		Defaults to half the camera's width and height.
		"""
		return (self._focus_center_x, self._focus_center_y)

	@focus_center.setter
	def focus_center(self, new_focus_center: CoordIndexable) -> None:
		self._focus_center_x = new_focus_center[0]
		self._focus_center_y = new_focus_center[1]
		self._ubo_needs_update = True

	@property
	def x(self) -> float:
		return self._x

	@x.setter
	def x(self, new_x: float) -> None:
		self._x = new_x
		self._ubo_needs_update = True

	@property
	def y(self) -> float:
		return self._y

	@y.setter
	def y(self, new_y: float) -> None:
		self._y = new_y
		self._ubo_needs_update = True

	@property
	def zoom(self) -> float:
		return self._zoom

	@zoom.setter
	def zoom(self, new_zoom: float) -> None:
		self._zoom = new_zoom
		self._ubo_needs_update = True

	def delete(self) -> None:
		pass


class Camera(SimpleCamera):
	"""
	Inherits the SimpleCamera to transform drawables through a UBO and
	also posesses a framebuffer that can be drawn to in an attempt at
	cloning the HaxeFlixel camera system:
	https://github.com/HaxeFlixel/flixel/blob/dev/flixel/FlxCamera.hx
	"""

	def __init__(self, x: int, y: int, w: int, h: int) -> None:
		super().__init__(w, h)

		self._screen_x = x
		"""Absolute x position of the camera's display quad."""
		self._screen_y = y
		"""Absolute y position of the camera's display quad."""

		self._width = w
		"""True pixel width of the camera's display quad."""
		self._height = h
		"""True pixel height of the camera's display quad."""

		self._rotation = 0
		"""Rotation of the camera's display quad. TODO: NOT IMPLEMENTED."""

		self._effect_shaders: t.List["ShaderProgram"] = []
		"""
		A list of shaders that will be sequentially applied to this
		camera's display quad.
		TODO: NOT IMPLEMENTED.
		"""

		self.clear_color = (0.0, 0.0, 0.0, 0.0)
		"""Color the camera's frame buffer is cleared with."""

		self.framebuffer = Framebuffer()
		self.texture = Texture.create(w, h)
		self.framebuffer.attach_texture(self.texture)

		self.program = self._shader_container.get_program()

		self.quad_vao = gl.GLuint()
		"""
		VAO that needs to be bound to properly render the camera's
		display quad.
		"""

		self.quad_vbo = BufferObject(gl.GL_ARRAY_BUFFER, _QUAD_VBO_SIZE, gl.GL_DYNAMIC_DRAW)
		"""
		VBO containing the vertices to properly render the camera's
		display quad.
		"""

		# Below is largely stolen from
		# https://learnopengl.com/Advanced-OpenGL/Framebuffers

		tex_coords = (ctypes.c_float * 12)(
			 0., 0.,
			 1., 0.,
			 0., 1.,
			 1., 1.,
			 0., 1.,
			 1., 0.,
		)
		self.quad_vbo.set_data_array(
			_QUAD_VBO_TEX_COORD_SEGMENT_START,
			_QUAD_VBO_TEX_COORD_SEGMENT_SIZE,
			tex_coords,
		)

		self.quad_vbo.set_data_array(
			_QUAD_VBO_FILL_COLOR_SEGMENT_START,
			_QUAD_VBO_FILL_COLOR_SEGMENT_SIZE,
			(ctypes.c_ubyte * 24)(),
		)

		gl.glCreateVertexArrays(1, ctypes.byref(self.quad_vao))
		# Enable vertex attribute indices
		gl.glEnableVertexArrayAttrib(self.quad_vao, 0)
		gl.glEnableVertexArrayAttrib(self.quad_vao, 1)
		gl.glEnableVertexArrayAttrib(self.quad_vao, 2)
		# Specify vertex layout for the attributes
		gl.glVertexArrayAttribFormat(self.quad_vao, 0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0)
		gl.glVertexArrayAttribFormat(self.quad_vao, 1, 2, gl.GL_FLOAT, gl.GL_FALSE, 0)
		gl.glVertexArrayAttribFormat(self.quad_vao, 2, 4, gl.GL_UNSIGNED_BYTE, gl.GL_TRUE, 0)
		# Associate the binding points with the buffer the vertices should be sourced from
		gl.glVertexArrayVertexBuffer(
			self.quad_vao,
			0,
			self.quad_vbo.id,
			_QUAD_VBO_POSITION_SEGMENT_START,
			2 * GL_TYPE_SIZES[gl.GL_FLOAT]
		)
		gl.glVertexArrayVertexBuffer(
			self.quad_vao,
			1,
			self.quad_vbo.id,
			_QUAD_VBO_TEX_COORD_SEGMENT_START,
			2 * GL_TYPE_SIZES[gl.GL_FLOAT],
		)
		gl.glVertexArrayVertexBuffer(
			self.quad_vao,
			2,
			self.quad_vbo.id,
			_QUAD_VBO_FILL_COLOR_SEGMENT_START,
			4 * GL_TYPE_SIZES[gl.GL_UNSIGNED_BYTE],
		)
		# Link the shader attribute index with the binding point
		gl.glVertexArrayAttribBinding(self.quad_vao, 0, 0)
		gl.glVertexArrayAttribBinding(self.quad_vao, 1, 1)
		gl.glVertexArrayAttribBinding(self.quad_vao, 2, 2)

		self._vbo_needs_update = True

	def draw_framebuffer(self) -> None:
		"""
		Draws the camera's framebuffer as a fullscreen quad.
		This changes the active program, the texture bound
		to `TEXTURE_2D` and the blend func.
		"""
		if self._vbo_needs_update:
			self._update_vbo()

		self.program.use()
		# self.program["camera_texture"] = 0
		gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
		gl.glBindVertexArray(self.quad_vao)
		gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)
		gl.glBindVertexArray(0)

	def _update_vbo(self) -> None:
		x1 = self._screen_x
		y1 = self._screen_y + self._height
		x2 = self._screen_x + self._width
		y2 = self._screen_y
		v = [
			(x1, y1), #0
			(x2, y1), #1
			(x1, y2), #2
			(x2, y2), #3
		]
		# Not going through the trouble of indexing (yet)
		data = (ctypes.c_float * 12)(*v[0], *v[1], *v[2], *v[3], *v[2], *v[1])
		self.quad_vbo.set_data_array(0, _QUAD_VBO_POSITION_SEGMENT_SIZE, data)
		self._vbo_needs_update = False

	@property
	def screen_x(self) -> float:
		return self._screen_x

	@screen_x.setter
	def screen_x(self, new_x: float) -> None:
		self._screen_x = new_x
		self._vbo_needs_update = True

	@property
	def screen_y(self) -> float:
		return self._screen_y

	@screen_y.setter
	def screen_y(self, new_y: float) -> None:
		self._screen_y = new_y
		self._vbo_needs_update = True

	@property
	def width(self) -> float:
		return self._width

	@width.setter
	def width(self, new_width: float) -> None:
		self._width = new_width
		self._vbo_needs_update = True

	@property
	def height(self) -> float:
		return self._height

	@height.setter
	def height(self, new_height: float) -> None:
		self._height = new_height
		self._vbo_needs_update = True

	def delete(self) -> None:
		self.framebuffer.delete()
		del self.framebuffer
		self.texture.delete()
		del self.texture
		self.quad_vbo.delete()
		del self.quad_vbo
		gl.glDeleteVertexArrays(1, ctypes.byref(self.quad_vao))
