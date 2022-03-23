
import typing as t
from loguru import logger

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.constants import PIXEL_TEXTURE
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.core.tweens import TWEEN_ATTR, in_out_quart
from pyday_night_funkin.core.utils import to_rgb_tuple
from pyday_night_funkin.enums import CONTROL


class PauseScene(BaseScene):
	"""
	Cheap menu scene that destroys itself when button is pressed.
	"""

	def __init__(self, game) -> None:
		super().__init__(game)

		self.background = self.create_object("bg", image=PIXEL_TEXTURE)
		self.background.scale_x = CNST.GAME_WIDTH
		self.background.scale_y = CNST.GAME_HEIGHT
		self.background.color = to_rgb_tuple(CNST.BLACK)
		self.background.opacity = 0
		self.background.start_tween(in_out_quart, {TWEEN_ATTR.OPACITY: 153}, 0.4)

		self.add(TextLine("<PAUSED>", bold=True, x=910, y=650), "fg")

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.ENTER):
			self.remove_scene(False)
		elif self.game.key_handler.just_pressed(CONTROL.BACK):
			self.remove_scene(True)
