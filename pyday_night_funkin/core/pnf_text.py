"""
Custom text module.
Less able that pyglet's text module (i.e. lacks HTML highlighting
and does not come close to its document abstractions), but works
with the PNF graphics backend and should also run a bit faster.
Attempts to mock the API of HaxeFlixel's FlxText.
Known to fail with:
	- Non-left-to-right writing systems
	- "Zalgo" text
"""

# Module is a dysfunctional hack as of now (17.03.2022),
# but I'm confident there will be something in like 2 weeks

from enum import IntEnum
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
in vec2 translate;
in vec2 scale;
in vec2 scroll_factor;
in vec3 tex_coords;
in vec4 colors;
in float rotation;

out vec4 frag_colors;
out vec3 frag_tex_coords;

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
	m_trans_scale[3].xy = translate;
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

	frag_colors = colors;
	frag_tex_coords = tex_coords;
}
"""

_PNF_TEXT_FRAGMENT_SOURCE = """
#version 450

in vec4 frag_colors;
in vec3 frag_tex_coords;

out vec4 final_color;

uniform sampler2D sprite_texture;


void main() {
	final_color = vec4(frag_colors.rgb, texture(sprite_texture, frag_tex_coords.xy).a);
}
"""

class _Line:
	"""
	Small line dataclass for text layout.
	"""

	def __init__(self) -> None:
		pass

class ALIGNMENT(IntEnum):
	LEFT = 0
	CENTER = 1
	RIGHT = 2


class PNFText(WorldObject):

	shader_container = ShaderContainer(_PNF_TEXT_VERTEX_SOURCE, _PNF_TEXT_FRAGMENT_SOURCE)

	def __init__(
		self,
		x: int = 0,
		y: int = 0,
		text: str = "",
		font_size: int = 8,
		font_name: t.Optional[str] = None,
		color: t.Tuple[int, int, int, int] = (0x00, 0x00, 0x00, 0xFF),
		multiline: bool = False,
		field_width: int = 0,
		alignment: ALIGNMENT = ALIGNMENT.LEFT,
		context: t.Optional[SceneContext] = None,
	) -> None:
		super().__init__(x, y)

		self._context = (
			SceneContext() if context is None
			else SceneContext(context.batch, PNFGroup(parent=context.group), context.cameras)
		)
		self._text = text
		self._font_name = font_name
		self._font_size = font_size
		self._color = color

		self._interfacer = None
		self._create_interfacer()

	def set_format(self) -> None:
		pass

	def _build_state(self, ftex: "Texture", cam: "Camera") -> state.GLState:
		"""
		Builds a GLState for the given camera.
		"""
		return state.GLState.from_state_parts(
			state.ProgramStatePart(self.shader_container.get_program()),
			state.TextureUnitStatePart(gl.GL_TEXTURE0),
			state.TextureStatePart(ftex),
			state.UBOBindingStatePart(cam.ubo),
			state.EnableStatePart(gl.GL_BLEND),
			state.BlendFuncStatePart(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA),
		)

	def _create_interfacer(self) -> None:
		# TODO: platform specific type hint, remove
		font_tex: "Win32DirectWriteFont" = load_font(self._font_name, self._font_size)

		glyphs: t.List["Glyph"] = font_tex.get_glyphs(self._text)

		x_advance = 0
		indices = []
		vertices = []
		tex_coords = []
		owner = None
		for i, glyph in enumerate(glyphs):
			indices += [x + (i * 4) for x in (0, 1, 2, 0, 2, 3)]
			v0: "Numeric"
			v1: "Numeric"
			v2: "Numeric"
			v3: "Numeric"
			# v3 and v1 swapped as glyph.vertices assumes bottom-left origin
			v0, v3, v2, v1 = glyph.vertices

			v0 += x_advance
			v2 += x_advance
			vertices += [v0, v1, v2, v1, v2, v3, v0, v3]

			tex_coords.extend(glyph.tex_coords)
			x_advance += glyph.advance
			if owner is None:
				owner = glyph.owner
			elif owner is not glyph.owner:
				raise RuntimeError("booo")

		# NOTE: Still no idea how stuff works exactly, adding this as a workaround
		# for empty strings
		if owner is None:
			owner = load_font().get_glyphs("A")[0].owner

		vertex_amt = 4 * len(glyphs)
		self._interfacer = self._context.batch.add_indexed(
			vertex_amt,
			gl.GL_TRIANGLES,
			self._context.group,
			indices,
			{cam: self._build_state(owner, cam) for cam in self._context.cameras},
			("position2f/", vertices),
			("translate2f/", (self._x, self._y) * vertex_amt),
			("tex_coords3f/", tex_coords),
			("scale2f/", (1.0, 1.0) * vertex_amt),
			("scroll_factor2f/", (1.0, 1.0) * vertex_amt),
			("rotation1f/", (0.0,) * vertex_amt),
			("colors4B/", self._color * vertex_amt),
		)

	def _relayout_lines(self) -> None:
		pass

	def set_context(self, parent_context: "SceneContext") -> None:
		self._context = SceneContext(
			parent_context.batch, PNFGroup(parent=parent_context.group), parent_context.cameras
		)
		self._interfacer.delete()
		self._create_interfacer()

	def delete(self) -> None:
		super().delete()
		self._interfacer.delete()
		self._interfacer = None

	@property
	def text(self) -> str:
		return self._text

	@text.setter
	def text(self, new_text: str) -> None:
		self._text = new_text
		self._interfacer.delete()
		self._create_interfacer()

	@property
	def x(self) -> "Numeric":
		return self._x

	@x.setter
	def x(self, new_x: "Numeric") -> None:
		self._x = new_x
		self._interfacer.set_data("translate", (new_x, self._y) * self._interfacer.size)

	@property
	def y(self) -> "Numeric":
		return self._y

	@y.setter
	def y(self, new_y: "Numeric") -> None:
		self._y = new_y
		self._interfacer.set_data("translate", (self._x, new_y) * self._interfacer.size)
