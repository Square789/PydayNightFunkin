"""
Custom text module. Less able that pyglet's text module
(i.e. lacks HTML highlighting and does not come close to its document
abstractions), but works with the PNF graphics backend and should also
run a bit faster. Probably incompatible with non-western fonts as well.
"""

import typing as t

from pyglet.font import load as load_font

from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.scene_object import WorldObject

if t.TYPE_CHECKING:
	from pyglet.font import Win32DirectWriteFont
	from pyglet.font.base import Glyph



class PNFText(WorldObject):
	def __init__(
		self,
		font_name: str,
		text: str,
		context: t.Optional[Context] = None,
	) -> None:
		context = Context() if context is None else context

		# TODO: platformspecific type hint, remove
		font_tex: "Win32DirectWriteFont" = load_font(font_name)

		glyphs: t.List["Glyph"] = font_tex.get_glyphs(text)

		for glyph in glyphs:
			print(vars(glyph))

