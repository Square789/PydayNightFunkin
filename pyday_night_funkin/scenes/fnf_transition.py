
import typing as t

from pyglet.gl import gl
from pyglet.image import ImageData

from pyday_night_funkin.core.graphics.samplers import get_sampler
from pyday_night_funkin.core.graphics import state as s
from pyday_night_funkin.core.pnf_sprite import PNFSprite, PNFSpriteVertexShader
from pyday_night_funkin.core.shaders import ShaderContainer
from pyday_night_funkin.core.scene import TransitionScene
from pyday_night_funkin.core.utils import to_rgba_bytes

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import UniformBufferObject


# https://stackoverflow.com/questions/47376499/creating-a-gradient-color-in-fragment-shader
_GRADIENT_SPRITE_FRAGMENT_SHADER_SOURCE = """
#version 450

in vec4 vertex_colors;
in vec3 texture_coords;

out vec4 final_color;

uniform sampler2D gradient_texture;
uniform float gradient_width;

void main() {
	float gradient_progress = abs(texture_coords.y - 1.0);

	final_color = texture(
		gradient_texture,
		vec2((gradient_progress * (gradient_width - 1.0) + 0.5) / gradient_width, 0.5)
	);
}
"""

_GRADIENT_SHADER_CONTAINER = ShaderContainer(
	PNFSpriteVertexShader.generate(),
	_GRADIENT_SPRITE_FRAGMENT_SHADER_SOURCE
)

class GradientSprite(PNFSprite):
	shader_container = _GRADIENT_SHADER_CONTAINER

	def __init__(self, gradient_colors: t.List[int], *args, **kwargs) -> None:
		self._gradient_texture = ImageData(
			len(gradient_colors),
			1,
			"RGBA",
			b"".join(to_rgba_bytes(color) for color in gradient_colors)
		).get_texture()
		kwargs["image"] = self._gradient_texture

		self._gradient_width = float(len(gradient_colors))

		super().__init__(*args, **kwargs)

	def _build_gl_state(self, cam_ubo: "UniformBufferObject") -> s.GLState:
		p = self.shader_container.get_program()

		return s.GLState.from_state_parts(
			s.ProgramStatePart(p),
			s.UBOBindingStatePart(cam_ubo),
			s.TextureUnitStatePart(gl.GL_TEXTURE0),
			s.SamplerBindingState(0, get_sampler(self._nearest_sampling)),
			s.TextureStatePart(self._texture),
			s.UniformStatePart.from_name_and_value(p, "gradient_width", self._gradient_width),
			s.EnableStatePart(gl.GL_BLEND),
			s.SeparateBlendFuncStatePart(
				self._blend_src, self._blend_dest, gl.GL_ONE, self._blend_dest
			),
		)

	def delete(self):
		super().delete()
		self._gradient_texture.delete()
		del self._gradient_texture


class FNFTransitionScene(TransitionScene):
	def create_transition_effect(self, is_in: bool, on_end: t.Callable[[], t.Any]) -> None:
		# This stuff is pretty specifically hardcoded to FNF's transition data.
		# See dev_notes/scene_transitions.txt towards the end for specifics.

		gradient_colors = [0x00000000, 0x000000FF, 0x000000FF, 0x000000FF]
		if not is_in:
			gradient_colors.reverse()

		# Values originated from original game's "region" for the TransitionData.
		# r_y just gets overwritten completely, so that one's irrelevant.
		r_x = -200
		r_w = int(self.game.dimensions[0] * 1.4)
		r_h = int(self.game.dimensions[1] * 1.4)

		self.gradient = self.create_object(
			object_class = GradientSprite,
			gradient_colors = gradient_colors,
			x = r_x,
			y = -r_h if is_in else -r_h * 2.0,
		)
		self.gradient.scale_x = r_w
		self.gradient.scale_y = r_h * 2.0
		self.gradient.recalculate_positioning()
		self.gradient.scroll_factor = (0.0, 0.0)

		time = 0.5 if is_in else 0.35
		if self.game.debug:
			time *= 0.75

		self.effects.tween(
			self.gradient,
			{"y": self.game.dimensions[1] if is_in else 0.0},
			time,
			on_complete = None if on_end is None else (lambda _: on_end()),
		)
