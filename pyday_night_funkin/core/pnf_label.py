"""
! WARNING !
Massive unstable copypaste-job that is not guaranteed to survive patch
versions.
Purpose is to get labels that are affected by cameras and can be added
to PNFBatches.
"""

import ast
import inspect
import typing as t

from loguru import logger
import pyglet
from pyglet.gl import gl
from pyglet.text import Label, decode_text
from pyglet.text.layout import (
	_GlyphBox, TextLayout, decoration_fragment_source, layout_fragment_source
)

from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup, states
from pyday_night_funkin.core.scene_object import SceneObject
from pyday_night_funkin.core.shaders import ShaderContainer

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram, UniformBufferObject
	from pyglet.image import Texture


if pyglet.version != "2.0.dev13":
	logger.warning("Incompatible pyglet version for label patch!")


# https://medium.com/@chipiga86/
# python-monkey-patching-like-a-boss-87d7ddb8098e
def get_src(o):
	src = inspect.getsource(o).split("\n")
	indent = len(src[0]) - len(src[0].lstrip())
	return "\n".join(l[indent:] for l in src)


class _TextPatcher(ast.NodeTransformer):
	def __init__(self, sub_what, sub_with) -> None:
		super().__init__()
		self.sub_what = sub_what
		self.sub_with = sub_with

	def visit_Name(self, node):
		if node.id != self.sub_what:
			return node
		return ast.Name(id = self.sub_with, ctx = node.ctx)


_tp = _TextPatcher("_GlyphBox", "_TLGlyphBox")

def _patch(src_cls, method_name):
	"""
	Changes all occurrences of `_GlyphBox` in the method
	`src_cls:method_name` to `_TLGlyphBox` and returns the recompiled
	method, which is bound to the global scope of the module the
	source class was defined in.
	"""
	src_mod = inspect.getmodule(src_cls)
	meth_ast = ast.parse(get_src(getattr(src_cls, method_name)))

	meth_ast = ast.fix_missing_locations(_tp.visit(meth_ast))

	src_mod.__dict__["_TLGlyphBox"] = _TLGlyphBox
	# Required so the recompiled function has access to the module's globals
	d = src_mod.__dict__
	exec(compile(meth_ast, f"<patch from {inspect.getfile(src_mod)}>", "exec"), d)
	m = d.pop(method_name)
	return m

#############################
### PATCHED SHADERS BELOW ###
#############################

layout_vertex_source = """
#version 330 core

in vec2 position;
in vec4 colors;
in vec3 tex_coords;
in vec2 translation;

out vec4 text_colors;
out vec2 texture_coords;
out vec4 vert_position;

uniform WindowBlock
{
	mat4 projection;
	mat4 view;
} window;

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
} camera;

mat4 m_trans_scale = mat4(1.0);
mat4 m_camera_trans_scale = mat4(1.0);
mat4 m_camera_pre_trans = mat4(1.0);

void main()
{
	m_trans_scale[3] = vec4(translation, 1.0, 1.0);
	// Camera transform and zoom scale
	m_camera_trans_scale[3][0] = (camera.zoom * -camera.position.x) + (camera.GAME_DIMENSIONS.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * -camera.position.y) + (camera.GAME_DIMENSIONS.y / 2);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;
	// Camera pre-scale-transform
	m_camera_pre_trans[3][0] = -camera.GAME_DIMENSIONS.x / 2;
	m_camera_pre_trans[3][1] = -camera.GAME_DIMENSIONS.y / 2;

	gl_Position =
		window.projection *
		window.view *
		m_camera_trans_scale *
		m_camera_pre_trans *
		m_trans_scale *
		vec4(position, 0, 1)
	;

	vert_position = vec4(position + translation, 0, 1);
	text_colors = colors;
	texture_coords = tex_coords.xy;
}
"""

decoration_vertex_source = """
#version 330 core

in vec2 position;
in vec4 colors;
in vec2 translation;

out vec4 vert_colors;
out vec4 vert_position;


uniform WindowBlock
{
	mat4 projection;
	mat4 view;
} window;

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
} camera;

mat4 m_trans_scale = mat4(1.0);
mat4 m_camera_trans_scale = mat4(1.0);
mat4 m_camera_pre_trans = mat4(1.0);

void main()
{
	m_trans_scale[3] = vec4(translation, 1.0, 1.0);
	// Camera transform and zoom scale
	m_camera_trans_scale[3][0] = (camera.zoom * -camera.position.x) + (camera.GAME_DIMENSIONS.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * -camera.position.y) + (camera.GAME_DIMENSIONS.y / 2);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;
	// Camera pre-scale-transform
	m_camera_pre_trans[3][0] = -camera.GAME_DIMENSIONS.x / 2;
	m_camera_pre_trans[3][1] = -camera.GAME_DIMENSIONS.y / 2;

	gl_Position =
		window.projection *
		window.view *
		m_camera_trans_scale *
		m_camera_pre_trans *
		m_trans_scale *
		vec4(position, 0, 1)
	;

	vert_position = vec4(position + translation, 0, 1);
	vert_colors = colors;
}
"""


_LAYOUT_SHADER_CONTAINER = ShaderContainer(layout_vertex_source, layout_fragment_source)
_DECORATION_SHADER_CONTAINER = ShaderContainer(decoration_vertex_source, decoration_fragment_source)

############################
### PATCHED GROUPS BELOW ###
############################

class PNFTextLayoutGroup(PNFGroup):
	def __init__(
		self,
		texture: "Texture",
		program: "ShaderProgram",
		cam_ubo: "UniformBufferObject",
		parent: t.Optional[PNFGroup] = None,
		order: int = 0,
	) -> None:
		super().__init__(
			parent,
			order,
			states.GLState(
				states.ProgramStatePart(program),
				states.UBOBindingStatePart(cam_ubo),
				states.UniformStatePart("scissor", False),
				states.TextureUnitStatePart(gl.GL_TEXTURE0),
				states.TextureStatePart(texture),
				states.EnableStatePart(gl.GL_BLEND),
				states.BlendFuncStatePart(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA),
			),
		)


class PNFTextDecorationGroup(PNFGroup):
	def __init__(
		self,
		program: "ShaderProgram",
		cam_ubo: "UniformBufferObject",
		parent: t.Optional[PNFGroup] = None,
		order: int = 0,
	) -> None:
		super().__init__(
			parent,
			order,
			states.GLState(
				states.ProgramStatePart(program),
				states.UBOBindingStatePart(cam_ubo),
				states.UniformStatePart("scissor", False),
				states.EnableStatePart(gl.GL_BLEND),
				states.BlendFuncStatePart(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA),
			),
		)


###############################
### PATCHED GLYPH BOX BELOW ###
###############################

class _TLGlyphBox(_GlyphBox):
	def place(self, layout, i, x, y, context):
		assert self.glyphs

		try:
			group = layout.group_cache[self.owner]
		except KeyError:
			group = layout.group_class(
				self.owner,
				_LAYOUT_SHADER_CONTAINER.get_program(),
				layout._context.camera.ubo, # The more i work on this the worse it gets
				order=1,
				parent=layout.group,
			)
			layout.group_cache[self.owner] = group

		n_glyphs = self.length
		vertices = []
		tex_coords = []
		baseline = 0
		x1 = x
		for start, end, baseline in context.baseline_iter.ranges(i, i + n_glyphs):
			baseline = layout.parse_distance(baseline)
			assert len(self.glyphs[start - i:end - i]) == end - start
			for kern, glyph in self.glyphs[start - i:end - i]:
				x1 += kern
				vx1, vy1, vx2, vy2 = glyph.vertices

				# TOP LEFT MODIFICATION HERE #
				vy1, vy2 = vy2, vy1

				vx1 += x1
				vx2 += x1
				vy1 += y + baseline
				vy2 += y + baseline
				vertices.extend(map(int, [vx1, vy1, vx2, vy1, vx2, vy2, vx1, vy2]))
				t = glyph.tex_coords
				tex_coords.extend(t)
				x1 += glyph.advance

		# Text color
		colors = []
		for start, end, color in context.colors_iter.ranges(i, i + n_glyphs):
			if color is None:
				color = (0, 0, 0, 255)
			colors.extend(color * ((end - start) * 4))

		indices = []
		# Create indices for each glyph quad:
		for i in range(n_glyphs):
			indices.extend([element + (i * 4) for element in [0, 1, 2, 0, 2, 3]])

		vertex_list = layout.batch.add_indexed(
			n_glyphs * 4,
			gl.GL_TRIANGLES,
			group,
			indices,
			('position2f/dynamic', vertices),
			('colors4Bn/dynamic', colors),
			('tex_coords3f/dynamic', tex_coords),
			'translation2f/dynamic',
		)

		context.add_list(vertex_list)

		# NOTE: The stuff below isn't flipped around because I don't use it

		# Decoration (background color and underline)
		# -------------------------------------------
		# Should iterate over baseline too, but in practice any sensible
		# change in baseline will correspond with a change in font size,
		# and thus glyph run as well.  So we cheat and just use whatever
		# baseline was seen last.
		background_vertices = []
		background_colors = []
		underline_vertices = []
		underline_colors = []
		y1 = y + self.descent + baseline
		y2 = y + self.ascent + baseline
		x1 = x
		for start, end, decoration in context.decoration_iter.ranges(i, i + n_glyphs):
			bg, underline = decoration
			x2 = x1
			for kern, glyph in self.glyphs[start - i:end - i]:
				x2 += glyph.advance + kern

			if bg is not None:
				background_vertices.extend([x1, y1, x2, y1, x2, y2, x1, y2])
				background_colors.extend(bg * 4)

			if underline is not None:
				underline_vertices.extend([x1, y + baseline - 2, x2, y + baseline - 2])
				underline_colors.extend(underline * 2)

			x1 = x2

		if background_vertices:
			background_list = layout.batch.add_indexed(
				len(background_vertices) // 2,
				gl.GL_TRIANGLES,
				layout.background_decoration_group,
				[0, 1, 2, 0, 2, 3],
				('position2f/dynamic', background_vertices),
				('colors4Bn/dynamic', background_colors),
				'translation2f/dynamic',
			)
			context.add_list(background_list)

		if underline_vertices:
			underline_list = layout.batch.add(
				len(underline_vertices) // 2,
				gl.GL_LINES,
				layout.foreground_decoration_group,
				('position2f/dynamic', underline_vertices),
				('colors4Bn/dynamic', underline_colors),
				'translation2f/dynamic',
			)
			context.add_list(underline_list)


###########################
### PATCHED LABEL BELOW ###
###########################

class PNFLabel(Label, SceneObject):

	group_class = PNFTextLayoutGroup
	decoration_class = PNFTextDecorationGroup

	_flow_glyphs_single_line = _patch(TextLayout, "_flow_glyphs_single_line")
	_flow_glyphs_wrap = _patch(TextLayout, "_flow_glyphs_wrap")

	# This is an amalgamation of the __init__ methods of `Label`'s inheritance path.
	def __init__(
		self,
		text="",
		font_name=None,
		font_size=None,
		bold=False,
		italic=False,
		stretch=False,
		color=(255, 255, 255, 255),
		x=0,
		y=0,
		width=None,
		height=None,
		anchor_x='left',
		anchor_y='baseline',
		align='left',
		multiline=False,
		dpi=None,
		context=None,
		wrap_lines=True,
	) -> None:
		self._context = context or Context()

		# === NOTE: Copypaste of `pyglet.text.__init__.Label:__init__`
		document = decode_text(text)

		# === NOTE: Copypaste of `pyglet.text.layout.TextLayout:__init__`
		self.content_width = 0
		self.content_height = 0

		# NOTE: Set _user_group whenever context's group changes
		self._user_group = self._context.group

		decoration_shader = _DECORATION_SHADER_CONTAINER.get_program()
		self.background_decoration_group = self.decoration_class(
			decoration_shader, self._context.camera.ubo, order=0, parent=self._user_group
		)
		self.foreground_decoration_group = self.decoration_class(
			decoration_shader, self._context.camera.ubo, order=2, parent=self._user_group
		)

		self.group_cache = {}

		# Should not happen as contexts will always have a default batch.
		# if self._context.batch is None:
		# 	batch = PNFBatch()
		# 	self._own_batch = True

		# NOTE: Set _batch whenever context's batch changes.
		self._batch = self._context.batch

		self._width = width
		self._height = height
		self._multiline = multiline

		# Alias the correct flow method:
		self._flow_glyphs = self._flow_glyphs_wrap if multiline else self._flow_glyphs_single_line

		self._wrap_lines_flag = wrap_lines
		self._wrap_lines_invariant()

		self._dpi = dpi or 96
		self.document = document

		# === NOTE: Copypaste of `pyglet.text.__init__.DocumentLabel:__init__`
		self._x = x
		self._y = y
		self._anchor_x = anchor_x
		self._anchor_y = anchor_y
		self._update()

		# === NOTE: Copypaste of `pyglet.text.__init__.Label:__init__`
		self.document.set_style(0, len(self.document.text), {
			'font_name': font_name,
			'font_size': font_size,
			'bold': bold,
			'italic': italic,
			'stretch': stretch,
			'color': color,
			'align': align,
		})

	def update(self, dt: float) -> None:
		pass

	def set_context(self, parent_context: "Context") -> None:
		new_batch = parent_context.batch
		old_batch = self._context.batch
	
		change_batch = new_batch != old_batch

		if (
			parent_context.camera != self._context.camera or
			parent_context.group != self._context.group.parent
		):
			raise RuntimeError(
				"Labels can't change their group, unfortunately you'll have to recreate them."
			)

		if change_batch:
			self._context.batch = new_batch
			self._batch = new_batch
			self._own_batch = False
			self._update()

	def invalidate_context(self) -> None:
		pass

	def delete(self) -> None:
		super().delete()
		self._context = None
