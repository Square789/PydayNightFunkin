"""
Massive copypaste-job that is not guaranteed to survive patch versions
with only purpose to get top-left based labels.
"""

import ast
import inspect

from pyglet.gl import GL_LINES, GL_TRIANGLES
from pyglet.graphics import Batch
from pyglet.text import Label, decode_text
from pyglet.text.layout import _GlyphBox, TextLayout, get_default_layout_shader, TextDecorationGroup


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
				v0, v1, v2, v3 = glyph.vertices
				v0 += x1
				v2 += x1
				v1 += y + baseline
				v3 += y + baseline
				vertices.extend(map(int, [v0, v1, v2, v1, v2, v3, v0, v3]))
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


def get_src(o):
	src = inspect.getsource(o).split("\n")
	indent = len(src[0]) - len(src[0].lstrip())
	return "\n".join(l[indent:] for l in src)

class _TextPatcher(ast.NodeTransformer):
	def visit_Name(self, node):
		if node.id != "_GlyphBox":
			return node
		return ast.Name(id = "_TLGlyphBox", ctx = node.ctx)

_tp = _TextPatcher()

# https://medium.com/@chipiga86/
# python-monkey-patching-like-a-boss-87d7ddb8098e
def _patch(src_cls, method_name, tgt_cls):
	src_method = getattr(src_cls, method_name)
	src_mod = inspect.getmodule(src_method)
	meth_ast = ast.parse(get_src(src_method))

	meth_ast = ast.fix_missing_locations(_tp.visit(meth_ast))

	src_mod.__dict__["_TLGlyphBox"] = _TLGlyphBox
	d = src_mod.__dict__
	exec(compile(meth_ast, "<asdf>", "exec"), d)
	m = d.pop(method_name)
	return m

class TLTextLayout(TextLayout):
	_flow_glyphs_single_line = _patch(TextLayout, "_flow_glyphs_single_line", "TLTextLayout")
	_flow_glyphs_wrap = _patch(TextLayout, "_flow_glyphs_wrap", "TLTextLayout")


class TLDocumentLabel(TLTextLayout):
	def __init__(
		self, document=None,
		x=0, y=0, width=None, height=None,
		anchor_x='left', anchor_y='baseline',
		multiline=False, dpi=None, batch=None, group=None
	):
		super(TLDocumentLabel, self).__init__(
			document, width=width, height=height,
			multiline=multiline,
			dpi=dpi, batch=batch, group=group
		)

		self._x = x
		self._y = y
		self._anchor_x = anchor_x
		self._anchor_y = anchor_y
		self._update()

	# TODO: USE THIS TO ISOLATE ONLY DOCUMENTLABEL'S ATTRIBUTES, then work with that in __new__
	#       TO ELIMINATE COPY-PASTE
	# >>> set(dir(DocumentLabel)) - set(dir(TextLayout))
	# {'font_size', 'italic', 'bold', 'set_style', 'color', 'text', 'font_name', 'get_style'}

	@property
	def text(self):
		"""The text of the label.

		:type: str
		"""
		return self.document.text

	@text.setter
	def text(self, text):
		self.document.text = text

	@property
	def color(self):
		return self.document.get_style('color')

	@color.setter
	def color(self, color):
		self.document.set_style(0, len(self.document.text), {'color': color})

	@property
	def font_name(self):
		return self.document.get_style('font_name')

	@font_name.setter
	def font_name(self, font_name):
		self.document.set_style(0, len(self.document.text), {'font_name': font_name})

	@property
	def font_size(self):
		return self.document.get_style('font_size')

	@font_size.setter
	def font_size(self, font_size):
		self.document.set_style(0, len(self.document.text), {'font_size': font_size})

	@property
	def bold(self):
		return self.document.get_style('bold')

	@bold.setter
	def bold(self, bold):
		self.document.set_style(0, len(self.document.text), {'bold': bold})

	@property
	def italic(self):
		return self.document.get_style('italic')

	@italic.setter
	def italic(self, italic):
		self.document.set_style(0, len(self.document.text), {'italic': italic})

	def get_style(self, name):
		return self.document.get_style_range(name, 0, len(self.document.text))

	def set_style(self, name, value):
		self.document.set_style(0, len(self.document.text), {name: value})


class TLLabel(TLDocumentLabel):

	def __init__(
		self,
		text='', font_name=None, font_size=None, bold=False, italic=False, stretch=False,
		color=(255, 255, 255, 255),
		x=0, y=0, width=None, height=None,
		anchor_x='left', anchor_y='baseline',
		align='left',
		multiline=False, dpi=None, batch=None, group=None
	):
		document = decode_text(text)
		super(TLLabel, self).__init__(
			document, x, y, width, height,
			anchor_x, anchor_y,
			multiline, dpi, batch, group
		)

		self.document.set_style(0, len(self.document.text), {
			'font_name': font_name,
			'font_size': font_size,
			'bold': bold,
			'italic': italic,
			'stretch': stretch,
			'color': color,
			'align': align,
		})

