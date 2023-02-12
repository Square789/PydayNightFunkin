
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.core.tweens import in_out_quart
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.enums import CONTROL


class PauseScene(BaseScene):
	"""
	Cheap menu scene that destroys itself when button is pressed.
	"""

	def __init__(self, game) -> None:
		super().__init__(game)

		self.background = self.create_object("bg")
		self.background.make_rect(to_rgba_tuple(CNST.BLACK), CNST.GAME_WIDTH, CNST.GAME_HEIGHT)
		self.background.opacity = 0
		self.background.start_tween(in_out_quart, {"opacity": 153}, 0.4)

		self.add(TextLine("<PAUSED>", bold=True, x=910, y=650), "fg")

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "fg")

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.ENTER):
			self.remove_scene(False)
		elif self.game.key_handler.just_pressed(CONTROL.BACK):
			self.remove_scene(True)
