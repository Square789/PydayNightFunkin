
import typing as t

from pyglet.gl import gl
from pyglet.math import Mat4
from pyglet.window import Window

from pyday_night_funkin import constants as CNST

if t.TYPE_CHECKING:
	from pyday_night_funkin.types import Numeric


class PNFWindow(Window):
	"""
	Top left projection window that manages the viewport as well.
	Whether it should be doing that is a good question but all seems
	good so far.
	"""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.projection = Mat4.orthogonal_projection(
			0, CNST.GAME_WIDTH, CNST.GAME_HEIGHT, 0, -1, 1
		)

	def on_resize(self, width: "Numeric", height: "Numeric") -> None:
		cur_wh_ratio = width / height if height > 0 else 999
		tgt_wh_ratio = CNST.GAME_WIDTH / CNST.GAME_HEIGHT

		if cur_wh_ratio > tgt_wh_ratio:
			# height is limiting
			viewport_height = height
			viewport_width = int(height * tgt_wh_ratio)
		else:
			# width is limiting
			viewport_width = width
			viewport_height = int(width * (1/tgt_wh_ratio))

		gl.glViewport(
			(width - viewport_width) // 2,
			(height - viewport_height) // 2,
			max(1, viewport_width),
			max(1, viewport_height),
		)

	def clear(self) -> None:
		gl.glClearColor(0, 0, 0, 1)
		super().clear()
