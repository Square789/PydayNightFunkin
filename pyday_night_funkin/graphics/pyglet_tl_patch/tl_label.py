"""
Massive copypaste-job that is not guaranteed to survive patch versions
with only purpose to get top-left based labels.
"""

import ast
import inspect

from pyglet.gl import GL_LINES, GL_TRIANGLES
from pyglet.text import Label
from pyglet.text.layout import _GlyphBox, TextLayout, get_default_layout_shader


class _TLGlyphBox(_GlyphBox):
	def place(self, layout, i, x, y, context):
		assert self.glyphs
		try:
			group = layout.groups[self.owner]
		except KeyError:
			group = layout.default_group_class(
				texture=self.owner, order=1,
				program=get_default_layout_shader(), parent=layout._group
			)
			layout.groups[self.owner] = group

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
			GL_TRIANGLES,
			group,
			indices,
			('position2f/dynamic', vertices),
			('colors4Bn/dynamic', colors),
			('tex_coords3f/dynamic', tex_coords),
			'translation2f/dynamic',
		)

		context.add_list(vertex_list)

		# NOTE: This stuff isn't flipped around because I don't use it

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
				GL_TRIANGLES,
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
				GL_LINES,
				layout.foreground_decoration_group,
				('position2f/dynamic', underline_vertices),
				('colors4Bn/dynamic', underline_colors),
				'translation2f/dynamic',
			)
			context.add_list(underline_list)


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

class TLLabel(Label):
	_flow_glyphs_single_line = _patch(TextLayout, "_flow_glyphs_single_line")
	_flow_glyphs_wrap = _patch(TextLayout, "_flow_glyphs_wrap")
