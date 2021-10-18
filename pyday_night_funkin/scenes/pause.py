
import typing as t

from pyglet.image import ImageData

from pyday_night_funkin.alphabet import create_text_line
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.scenes._base import BaseScene
from pyday_night_funkin.tweens import TWEEN_ATTR, in_out_quart


class PauseScene(BaseScene):
	"""
	Cheap menu scene that destroys itself when button is pressed.
	"""

	def __init__(self, game) -> None:
		super().__init__(game)

		pixel = ImageData(1, 1, "RGBA", b"\x00\x00\x00\xFF").get_texture()
		self.background = self.create_sprite("bg", image=pixel)
		self.background.scale_x = CNST.GAME_WIDTH
		self.background.scale_y = CNST.GAME_HEIGHT
		self.background.opacity = 0
		self.background.start_tween(in_out_quart, {TWEEN_ATTR.OPACITY: 153}, 0.4)

		create_text_line("<PAUSED>", self, "fg", bold=True, x=910, y=650)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.ENTER):
			self.destroy()
