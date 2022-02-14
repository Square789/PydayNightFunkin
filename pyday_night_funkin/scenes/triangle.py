"""
Extremely rudimentary test scene used for custom
batch debugging.
"""

import typing as t

from pyglet import gl
from pyglet.window.key import LEFT, UP, DOWN, RIGHT, X, Z

from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.graphics import PNFGroup
import pyday_night_funkin.core.graphics.state as st
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.core.scene_object import SceneObject
from pyday_night_funkin.core.shaders import ShaderContainer

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.types import Numeric


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

class Triangle(SceneObject):
	shader_container = ShaderContainer(vertex_shader, fragment_shader)

	def __init__(self, batch, group, cam_ubo, x, y) -> None:
		self._x = x
		self._y = y
		self.cam_ubo = cam_ubo

		self._context = Context(
			batch,
			PNFGroup(group, 0, self._build_gl_state()),
		)

		self._create_interfacer()

	def set_context(self, parent_context: "Context") -> None:
		self._context = Context(
			parent_context.batch,
			PNFGroup(parent_context.group, 0, self._build_gl_state()),
		)

	def _build_gl_state(self):
		return st.GLState(
			st.ProgramStatePart(self.shader_container.get_program()),
			st.UBOBindingStatePart(self.cam_ubo),
		)

	def _create_interfacer(self) -> None:
		self._interfacer = self._context.batch.add_indexed(
			3, gl.GL_TRIANGLES, self._context.group, [0, 1, 2],
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
	def __init__(self, game: "Game") -> None:
		super().__init__(game)

		ubo = self._default_camera.ubo
		self.tri0 = Triangle(self.batch, self.get_layer("main").get_group(), ubo, 0, 0.7)
		#self.tri1 = Triangle(self.batch, self.get_layer("main").get_group(), ubo, -20, 60)
		#self.tri2 = Triangle(self.batch, self.get_layer("main").get_group(), ubo, 200, 100)

		self.please_work = self.create_object(
			"main", None, image=load_asset(ASSET.IMG_NEWGROUNDS_LOGO), x=50, y=50
		)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (("main", True),)

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
