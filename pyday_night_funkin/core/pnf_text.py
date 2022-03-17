"""
Custom text module. Less able that pyglet's text module
(i.e. lacks HTML highlighting and does not come close to its document
abstractions), but works with the PNF graphics backend and should also
run a bit faster. It closesly copies the API of HaxeFlixel's FlxText.
Probably incompatible with non-western fonts as well.
"""

# Module is a dysfunctional hack as of now (17.03.2022),
# but I'm confident there will be something in like 2 weeks

import typing as t

from pyglet.font import load as load_font
from pyglet.gl import gl

from pyday_night_funkin.core.graphics import state
from pyday_night_funkin.core.graphics.pnf_group import PNFGroup
from pyday_night_funkin.core.scene_context import SceneContext
from pyday_night_funkin.core.scene_object import WorldObject
from pyday_night_funkin.core.shaders import ShaderContainer

if t.TYPE_CHECKING:
	from pyglet.font import Win32DirectWriteFont
	from pyglet.font.base import Glyph
	from pyglet.image import Texture
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.types import Numeric


_PNF_TEXT_VERTEX_SOURCE = """
#version 450

in vec2 position;
in vec3 tex_coords;
in vec2 scale;
in vec2 scroll_factor;
in float rotation;

out vec4 vertex_colors;
out vec3 texture_coords;

uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
} camera;


mat4 m_trans_scale = mat4(1.0);
mat4 m_rotation = mat4(1.0);
mat4 m_camera_trans_scale = mat4(1.0);


void main() {
	m_trans_scale[0][0] = scale.x;
	m_trans_scale[1][1] = scale.y;
	m_rotation[0][0] =  cos(-radians(rotation));
	m_rotation[0][1] =  sin(-radians(rotation));
	m_rotation[1][0] = -sin(-radians(rotation));
	m_rotation[1][1] =  cos(-radians(rotation));
	// Camera transform and zoom scale
	m_camera_trans_scale[3][0] = (
		(camera.zoom * -camera.GAME_DIMENSIONS.x / 2) +
		(camera.zoom * scroll_factor.x * -camera.position.x) +
		(camera.GAME_DIMENSIONS.x / 2)
	);
	m_camera_trans_scale[3][1] = (
		(camera.zoom * -camera.GAME_DIMENSIONS.y / 2) +
		(camera.zoom * scroll_factor.y * -camera.position.y) +
		(camera.GAME_DIMENSIONS.y / 2)
	);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;

	gl_Position =
		window.projection *
		window.view *
		m_camera_trans_scale *
		m_trans_scale *
		m_rotation *
		vec4(position, 0, 1)
	;

	texture_coords = tex_coords;
}
"""

_PNF_TEXT_FRAGMENT_SOURCE = """
#version 450

in vec4 vertex_colors;
in vec3 texture_coords;

out vec4 final_color;

uniform sampler2D sprite_texture;


void main() {
	final_color = vec4(texture(sprite_texture, texture_coords.xy));
}
"""


class PNFText(WorldObject):

	shader_container = ShaderContainer(_PNF_TEXT_VERTEX_SOURCE, _PNF_TEXT_FRAGMENT_SOURCE)

	def __init__(
		self,
		font_name: str,
		text: str,
		context: t.Optional[SceneContext] = None,
	) -> None:
		self._x = 100
		self._y = 100
		self._context = (
			SceneContext() if context is None
			else SceneContext(context.batch, PNFGroup(parent=context.group), context.cameras)
		)
		self._text = text
		self._font_name = font_name
		self._interfacer = None
		self._create_interfacer()

	def _build_state(self, ftex: "Texture", cam: "Camera") -> state.GLState:
		"""
		Builds a GLState for the given camera.
		"""
		print(ftex)
		return state.GLState.from_state_parts(
			state.ProgramStatePart(self.shader_container.get_program()),
			state.TextureUnitStatePart(gl.GL_TEXTURE0),
			state.TextureStatePart(ftex),
			state.UBOBindingStatePart(cam.ubo),
		)

	def _create_interfacer(self) -> None:
		# TODO: platformspecific type hint, remove
		font_tex: "Win32DirectWriteFont" = load_font(self._font_name)

		glyphs: t.List["Glyph"] = font_tex.get_glyphs(self._text)

		for char, glyph in zip(self._text, glyphs):
			print(char, vars(glyph))

		x, y = self._x, self._y
		indices = []
		vertices = []
		tex_coords = []
		for i, glyph in enumerate(glyphs):
			indices += [x + (i * 4) for x in (0, 1, 2, 0, 2, 3)]
			v0: "Numeric"
			v1: "Numeric"
			v2: "Numeric"
			v3: "Numeric"
			v0, v1, v2, v3 = glyph.vertices

			v0 += x
			v2 += x
			v1 += y
			v3 += y
			vertices += [v0, v1, v2, v1, v2, v3, v0, v3]

			tex_coords.extend(glyph.tex_coords)
			x += glyph.advance

		self._interfacer = self._context.batch.add_indexed(
			len(vertices),
			gl.GL_TRIANGLES,
			self._context.group,
			indices,
			{cam: self._build_state(font_tex.textures[0], cam) for cam in self._context.cameras},
			("position2f/", vertices),
			("tex_coords3f/", tex_coords),
			("scale2f/", (0.0, 0.0) * 4 * len(glyphs)),
			("scroll_factor2f/", (1.0, 1.0) * 4 * len(glyphs)),
			("rotation1f/", (0.0,) * 4 * len(glyphs)),
		)

	def delete(self) -> None:
		super().delete()
		self._interfacer.delete()
		self._interfacer = None
