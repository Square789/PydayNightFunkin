"""
Extremely rudimentary test scene used for custom
batch debugging.
"""

import typing as t

from pyglet import gl
from pyglet.window.key import LEFT, UP, DOWN, RIGHT, X, Z

import pyday_night_funkin.core.graphics.state as st
from pyday_night_funkin.core.scene import BaseScene, SceneKernel
from pyday_night_funkin.core.scene_context import CamSceneContext
from pyday_night_funkin.core.scene_object import WorldObject
from pyday_night_funkin.core.shaders import ShaderContainer

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.types import Numeric



vertex_shader = """
#version 450
in vec2 position;
in vec3 color;

out vec3 color_vo;


uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

layout(std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  dimensions;
	vec2  focus_center;
} camera;

mat4 m_camera_trans_scale = mat4(1.0);
mat4 m_camera_pre_trans = mat4(1.0);

void main() {
	m_camera_trans_scale[3][0] = (camera.zoom * -camera.position.x) + (camera.dimensions.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * -camera.position.y) + (camera.dimensions.y / 2);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;

	m_camera_pre_trans[3][0] = -camera.dimensions.x / 2;
	m_camera_pre_trans[3][1] = -camera.dimensions.y / 2;

	color_vo = color;
	gl_Position =
		window.projection *
		window.view *
		m_camera_trans_scale *
		m_camera_pre_trans *
		vec4(position.xy, 0.0, 1.0)
	;
}
"""

fragment_shader = """
#version 450
in vec3 color_vo;
out vec4 color_fo;

void main() {
	color_fo = vec4(color_vo, 1.0);
}

"""

class Triangle(WorldObject):
	shader_container = ShaderContainer(vertex_shader, fragment_shader)

	def __init__(self, context, x, y) -> None:
		super().__init__(x, y, context)

		self._create_interfacer()

	def set_cam_context(self, new_cam_context: CamSceneContext) -> None:
		self._context = new_cam_context
		self._interfacer.delete()
		self._create_interfacer()

	def _build_gl_state(self, cubo):
		return st.GLState.from_state_parts(
			st.ProgramStatePart(self.shader_container.get_program()),
			st.UBOBindingStatePart(cubo),
		)

	def _create_interfacer(self) -> None:
		self._interfacer = self._context.batch.add_indexed(
			3, gl.GL_TRIANGLES, self._context.group, [0, 1, 2],
			{camera: self._build_gl_state(camera.ubo) for camera in self._context.cameras},
			("position2f/dynamic", (
				self._x,         self._y,
				self._x + 100.0, self._y,
				self._x,         self._y + 100.0,
			)),
			("color3Bn/static", (170, 0, 0, 0, 170, 0, 0, 0, 170)),
		)

	@property
	def x(self) -> "Numeric":
		return self._x

	@x.setter
	def x(self, new_x: "Numeric") -> None:
		self._x = new_x
		self._interfacer.set_data(
			"position", (new_x, self._y, new_x + 100.0, self._y, new_x, self._y + 100.0)
		)

	@property
	def y(self) -> "Numeric":
		return self._y

	@y.setter
	def y(self, new_y: "Numeric") -> None:
		self._y = new_y
		self._interfacer.set_data(
			"position", (self._x, new_y, self._x + 100.0, new_y, self._x, new_y + 100.0)
		)


class TriangleScene(BaseScene):
	def __init__(self, kernel: "SceneKernel") -> None:
		super().__init__(kernel)

		self.camera = self.create_camera()

		self.tri0 = Triangle(self.get_context(), 0, 0.7)
		self.tri1 = Triangle(self.get_context(), -20, 60)
		self.tri2 = self.create_object(object_class=Triangle, x=200, y=100)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.raw_key_handler[LEFT]:
			self.camera.x -= 10
		if self.game.raw_key_handler[RIGHT]:
			self.camera.x += 10
		if self.game.raw_key_handler[DOWN]:
			self.camera.y += 10
		if self.game.raw_key_handler[UP]:
			self.camera.y -= 10
		if self.game.raw_key_handler[Z]:
			self.camera.zoom += .01
		if self.game.raw_key_handler[X]:
			self.camera.zoom -= .01
