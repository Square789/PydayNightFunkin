"""
Extremely rudimentary test scene used for custom
batch debugging.
"""

import struct
import typing as t

from pyglet import gl
from pyglet.window.key import LEFT, UP, DOWN, RIGHT, V, X, Z

from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.graphics import PNFGroup
import pyday_night_funkin.core.graphics.states as st
from pyday_night_funkin.core.scene_object import SceneObject
from pyday_night_funkin.core.shaders import ShaderContainer

from pyday_night_funkin.scenes import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game

vertex_shader = """
#version 450
in vec2 position;
in vec3 color;

out vec3 color_vo;


uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

// Not really sure about having GAME_DIMENSIONS here
// since it's by all means a constant

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
} camera;

mat4 m_camera_trans_scale = mat4(1.0);
mat4 m_camera_pre_trans = mat4(1.0);

void main() {
	m_camera_trans_scale[3][0] = (camera.zoom * -camera.position.x) + (camera.GAME_DIMENSIONS.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * -camera.position.y) + (camera.GAME_DIMENSIONS.y / 2);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;

	m_camera_pre_trans[3][0] = -camera.GAME_DIMENSIONS.x / 2;
	m_camera_pre_trans[3][1] = -camera.GAME_DIMENSIONS.y / 2;

	color_vo = color;
	gl_Position =
		window.projection *
		window.view *
		// m_camera_trans_scale *
		// m_camera_pre_trans *
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

class Triangle(SceneObject):
	shader_container = ShaderContainer(vertex_shader, fragment_shader)

	def __init__(self, batch, group, cam_ubo, x, y) -> None:
		self._x = x
		self._y = y
		self.cam_ubo = cam_ubo

		self._context = Context(
			batch, 
			PNFGroup(group, 0, self.build_mutators()),
		)

		self._create_vertex_list()

	def set_context(self, parent_context: "Context") -> None:
		self._context = Context(
			parent_context.batch,
			PNFGroup(parent_context.group, 0, self.build_mutators()),
		)

	def build_mutators(self):
		return [
			st.ProgramStateMutator(self.shader_container.get_program()),
			st.UBOBindingStateMutator(self.cam_ubo),
		]

	def _create_vertex_list(self) -> None:
		self._vl = self._context.batch.add_indexed(
			3, gl.GL_TRIANGLES, self._context.group, [0, 1, 2],
			("position2f/dynamic", (
				self._x,         self._y,
				self._x + 100.0, self._y,
				self._x,         self._y + 100.0,
			)),
			("color3Bn/static", (170, 0, 0, 0, 170, 0, 0, 0, 170)),
		)


class TriangleScene(BaseScene):
	def __init__(self, game: "Game") -> None:
		super().__init__(game)

		ubo = self._default_camera.ubo
		self.tri0 = Triangle(self.batch, self.get_layer("main").get_group(), ubo, 0, 0.7)
		self.tri1 = Triangle(self.batch, self.get_layer("main").get_group(), ubo, -20, 60)
		self.tri2 = Triangle(self.batch, self.get_layer("main").get_group(), ubo, 200, 100)
		# self.tri0 = Triangle(self.batch, None, ubo, 0, 0.7)
		# self.tri1 = Triangle(self.batch, None, ubo, -20, 60)
		# self.tri2 = Triangle(self.batch, None, ubo, 200, 100)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (("main", True), )

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.pyglet_ksh[LEFT]:
			self._default_camera.x -= 10
		if self.game.pyglet_ksh[RIGHT]:
			self._default_camera.x += 10
		if self.game.pyglet_ksh[DOWN]:
			self._default_camera.y += 10
		if self.game.pyglet_ksh[UP]:
			self._default_camera.y -= 10
		if self.game.pyglet_ksh[Z]:
			self._default_camera.zoom += .01
		if self.game.pyglet_ksh[X]:
			self._default_camera.zoom -= .01

		if self.game.pyglet_ksh[V]:
			print(self._default_camera.ubo.read())
			fmt = "f4x2f2f"
			print(struct.unpack(fmt, self._default_camera.ubo.read()[:struct.calcsize(fmt)]))

		# self._default_camera.ubo.buffer.bind()
		# self._default_camera.ubo.bind()
