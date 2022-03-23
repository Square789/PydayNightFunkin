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

# Module barely does its job as of 20.03, still lacking
# features and can be optimized to the moon and back [although
# for that use C-extensions and do it later.
# Remember: MAKE IT WORK. MAKE IT RIGHT. MAKE IT FAST]

from enum import IntEnum
import typing as t

from pyglet.font import load as load_font
from pyglet.gl import gl

from pyday_night_funkin.core.constants import MAX_ALPHA_SSBO_BINDING_IDX
from pyday_night_funkin.core.graphics import state
from pyday_night_funkin.core.scene import SceneContext
from pyday_night_funkin.core.scene_object import WorldObject
from pyday_night_funkin.core.shaders import ShaderContainer

if t.TYPE_CHECKING:
	from pyglet.font import Win32DirectWriteFont
	from pyglet.font.base import Glyph
	from pyglet.image import Texture
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.types import Numeric


_PNF_TEXT_VERTEX_SOURCE = """
#version 450

in vec2 position;
in vec2 translate;
in vec2 scale;
in vec2 scroll_factor;
in vec3 tex_coords;
in vec4 color;
in float rotation;

out vec4 frag_color;
out vec3 frag_tex_coords;

uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

layout(std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
} camera;


mat4 m_translate = mat4(1.0);
mat4 m_scale = mat4(1.0);
mat4 m_rotate = mat4(1.0);
mat4 m_camera_trans_scale = mat4(1.0);


void main() {
	m_translate[3].xy = translate;

	m_scale[0][0] = scale.x;
	m_scale[1][1] = scale.y;

	m_rotate[0][0] =  cos(-radians(rotation));
	m_rotate[0][1] =  sin(-radians(rotation));
	m_rotate[1][0] = -sin(-radians(rotation));
	m_rotate[1][1] =  cos(-radians(rotation));

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
		m_translate *
		m_rotate *
		m_scale *
		vec4(position, 0, 1)
	;

	frag_color = color;
	frag_tex_coords = tex_coords;
}
"""

# _PNF_TEXT_FRAGMENT_SOURCE = f"""
# #version 450

# in vec4 frag_color;
# in vec3 frag_tex_coords;

# layout(location = 0) out vec4 final_color;

# layout(binding = {MAX_ALPHA_SSBO_BINDING_IDX}) buffer MaxAlphaBuffer {{
# 	uint a[];
# }};
# layout(origin_upper_left, pixel_center_integer) in vec4 gl_FragCoord;

# uniform sampler2D sprite_texture;


# void main() {{
# 	final_color = vec4(frag_color.rgb, texture(sprite_texture, frag_tex_coords.xy).a);
# 	atomicMax(
# 		a[int(gl_FragCoord.x) + int(gl_FragCoord.y) * 1280],
# 		uint(clamp(final_color.a * 256, 0, 255))
# 	);
# }}
# """

_PNF_TEXT_FRAGMENT_SOURCE = f"""
#version 450

in vec4 frag_color;
in vec3 frag_tex_coords;

out vec4 final_color;

uniform sampler2D sprite_texture;

void main() {{
	final_color = vec4(frag_color.rgb, texture(sprite_texture, frag_tex_coords.xy).a);
}}
"""

class _Line:
	"""
	Line dataclass for text layout.
	"""
	def __init__(
		self,
		y_offset: int,
		glyphs: t.Sequence["Glyph"],
		width: int,
	) -> None:
		"""
		y_offset: Specifies line offset relative to the text.
		glyphs: Glyphs on this line.
		width: The exact width the glyphs take to be fully displayed.
		"""
		self.y_offset = y_offset
		self.glyphs = glyphs
		self.width = width


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
		color: t.Tuple[int, int, int, int] = (0xFF, 0xFF, 0xFF, 0xFF),
		multiline: bool = False,
		width: int = 0,
		align: ALIGNMENT = ALIGNMENT.LEFT,
		context: t.Optional[SceneContext] = None,
	) -> None:
		super().__init__(x, y)

		self._context = SceneContext() if context is None else context.inherit()
		self._text = text
		self._font_name = font_name
		self._font_size = font_size
		self._color = color
		self._autosize = width <= 0
		self._width = width
		self._multiline = multiline
		self._align = align

		self.content_width = 0
		"""
		Pixels the label's contents take up. This may be lower than
		the manually set width [TODO but never higher?].
		"""

		self.lines: t.List[_Line] = []
		self._layout_lines()

		self._interfacer = None
		self._create_interfacer()

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
		indices = []
		vertices = []
		tex_coords = []
		owner = (
			self.lines[0].glyphs[0].owner if self.lines and self.lines[0].glyphs
			else load_font().get_glyphs("A")[0].owner
		)
		i = 0
		for line in self.lines:
			x_advance = 0
			if self._align is not ALIGNMENT.LEFT:
				x_advance = (
					max(self._width - line.width, 0) /
					(2 if self._align is ALIGNMENT.CENTER else 1)
				)
			line_y_offset = line.y_offset
			for glyph in line.glyphs:
				v0: "Numeric"
				v1: "Numeric"
				v2: "Numeric"
				v3: "Numeric"
				# v3 and v1 swapped as glyph.vertices assumes bottom-left origin
				v0, v3, v2, v1 = glyph.vertices
				v0 += x_advance
				v2 += x_advance
				v1 += line_y_offset
				v3 += line_y_offset
				vertices += [v0, v1, v2, v1, v2, v3, v0, v3]
				x_advance += glyph.advance

				tex_coords.extend(glyph.tex_coords)

				indices += [x + (i * 4) for x in (0, 1, 2, 0, 2, 3)]
				i += 1

				if owner is not glyph.owner:
					raise RuntimeError("Booo!")

		vertex_amt = len(vertices) // 2
		self._interfacer = self._context.batch.add_indexed(
			vertex_amt,
			gl.GL_TRIANGLES,
			self._context.group,
			indices,
			{cam: self._build_state(owner, cam) for cam in self._context.cameras},
			("position2f/", vertices),
			("translate2f/", (self._x, self._y) * vertex_amt),
			("tex_coords3f/", tex_coords),
			("scale2f/", (self._scale * self._scale_x, self._scale * self._scale_y) * vertex_amt),
			("scroll_factor2f/", self._scroll_factor * vertex_amt),
			("rotation1f/", (self._rotation,) * vertex_amt),
			("color4Bn/", self._color * vertex_amt),
		)

	def _layout_lines(self) -> None:
		"""
		Lays out the PNFText's text in lines depending on whether it's
		single-or multiline.
		"""
		# TODO: platform specific type hint, remove
		font: "Win32DirectWriteFont" = load_font(self._font_name, self._font_size)
		if self._multiline:
			self.lines = []
			y_offset = 0
			for text_line in self._text.splitlines():
				glyphs: t.List["Glyph"] = font.get_glyphs(text_line)
				self.lines.append(_Line(y_offset, glyphs, sum(g.advance for g in glyphs)))
				y_offset += font.ascent
		else:
			glyphs: t.List["Glyph"] = font.get_glyphs(self._text)
			self.lines = [_Line(0, glyphs, sum(g.advance for g in glyphs))]

		self.content_width = max(l.width for l in self.lines)

	def set_context(self, parent_context: "SceneContext") -> None:
		self._context = parent_context.inherit()
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
		self._layout_lines()
		self._interfacer.delete()
		self._create_interfacer()

	# === Superclass property redefinitions below === #

	# Position

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

	@property
	def position(self) -> t.Tuple["Numeric", "Numeric"]:
		return (self._x, self._y)

	@position.setter
	def position(self, new_position: t.Tuple["Numeric", "Numeric"]) -> None:
		self._x, self._y = new_position
		self._interfacer.set_data("translate", new_position * self._interfacer.size)

	# Rotation

	@property
	def rotation(self) -> float:
		return self._rotation

	@rotation.setter
	def rotation(self, new_rotation: float) -> None:
		self._rotation = new_rotation
		self._interfacer.set_data("rotation", (new_rotation,) * 4)

	# Scale

	@property
	def scale_x(self) -> "Numeric":
		return self._scale_x

	@scale_x.setter
	def scale_x(self, new_scale_x: "Numeric") -> None:
		self._scale_x = new_scale_x
		self._interfacer.set_data(
			"scale", (self._scale * new_scale_x, self._scale * self._scale_y) * 4
		)

	@property
	def scale_y(self) -> "Numeric":
		return self._scale_y

	@scale_y.setter
	def scale_y(self, new_scale_y: "Numeric") -> None:
		self._scale_y = new_scale_y
		self._interfacer.set_data(
			"scale", (self._scale * self._scale_x, self._scale * new_scale_y) * 4
		)

	@property
	def scale(self) -> "Numeric":
		return self._scale

	@scale.setter
	def scale(self, new_scale: "Numeric") -> None:
		self._scale = new_scale
		self._interfacer.set_data(
			"scale",
			(new_scale * self._scale_x, new_scale * self._scale_y) * 4,
		)

	# Scroll factor

	@property
	def scroll_factor(self) -> t.Tuple[float, float]:
		return self._scroll_factor

	@scroll_factor.setter
	def scroll_factor(self, new_sf: t.Tuple[float, float]) -> None:
		self._scroll_factor = new_sf
		self._interfacer.set_data("scroll_factor", new_sf * 4)
