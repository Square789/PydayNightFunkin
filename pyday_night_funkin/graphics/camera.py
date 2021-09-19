
import typing as t

from pyglet.gl import *
from pyglet.graphics.shader import Shader, ShaderProgram

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH

if t.TYPE_CHECKING:
	from pyday_night_funkin.graphics.pnf_sprite import PNFSprite


CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)


class Camera:

	# https://github.com/pyglet/pyglet/blob/ \
	# a16674ff3f448379a8810d9f81c180af647a615e/pyglet/window/__init__.py#L441
	# Like here, apparently a never-used dummy shader is required to get a uniform
	# block
	_dummy_vertex_src = """
	#version 330
	in vec4 pos;

	uniform CameraAttrs {
		float zoom;
		vec2  deviance;
	} camera;

	void main() {
		gl_Position = camera.zoom * vec4(camera.deviance, 0, 1) * pos;
	}
	"""

	def __init__(self):
		self._view_target = list(CENTER)
		self._zoom = 1.0
		self._deviance = None

		self._dummy_shader = ShaderProgram(Shader(self._dummy_vertex_src, "vertex"))
		self.ubo = self._dummy_shader.uniform_blocks["CameraAttrs"].create_ubo()

		self._update_ubo()

	def _update_ubo(self):
		vx, vy = self._view_target
		zoom = self._zoom
		with self.ubo as ubo:
			ubo.deviance[:] = ((CENTER_X - vx), (CENTER_Y - vy))
			ubo.zoom = zoom

	@property
	def x(self) -> int:
		return self._view_target[0]

	@x.setter
	def x(self, new_x: int) -> None:
		self._view_target[0] = new_x
		self._update_ubo()

	@property
	def y(self) -> int:
		return self._view_target[1]

	@y.setter
	def y(self, new_y: int) -> None:
		self._view_target[1] = new_y
		self._update_ubo()

	@property
	def zoom(self) -> float:
		return self._zoom

	@zoom.setter
	def zoom(self, new_zoom: float) -> None:
		self._zoom = new_zoom
		self._update_ubo()
