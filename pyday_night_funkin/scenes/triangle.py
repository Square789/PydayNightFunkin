
import typing as t

from pyglet import gl

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

out vec4 color_vo;


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


void main() {
	color_vo = vec4(color, 1.0);
	gl_Position = vec4(position.xy, 0.0, 1.0);
}
"""

fragment_shader = """
#version 450
in vec4 color_vo;
out vec4 color_fo;

void main() {
	color_fo = color_vo;
}

"""

triangle_shader_container = ShaderContainer(vertex_shader, fragment_shader)


class Triangle(SceneObject):
	def __init__(self, batch, group) -> None:
		self._context = Context(
			batch, 
			PNFGroup(
				group,
				0,
				[st.ProgramStateMutator(triangle_shader_container.get_program())]
			),
		)
		self._create_vertex_list()


	def set_context(self, parent_context: "Context") -> None:
		self._context = Context(
			parent_context.batch,
			PNFGroup(
				parent_context.group,
				0,
				[st.ProgramStateMutator(triangle_shader_container.get_program())]
			),
		)

	def _create_vertex_list(self) -> None:
		self._vl = self._context.batch.add_indexed(
			3, gl.GL_TRIANGLES, self._context.group, [0, 1, 2],
			("position2f/dynamic", (1.0, 1.0, 100.0, 1.0, 1.0, 100.0)),
			("color3Bn/static", (170, 0, 0) * 3),
		)


class TriangleScene(BaseScene):
	def __init__(self, game: "Game") -> None:
		super().__init__(game)

		self.triangle = Triangle(self.batch, None)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("main", )
