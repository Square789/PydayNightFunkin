
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.tween_effects.eases import in_out_quart
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.enums import Control
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.scene import SceneKernel


class PauseScene(scenes.MusicBeatScene):
	"""
	Cheap menu scene that destroys itself when a button is pressed.
	"""

	def __init__(self, kernel: "SceneKernel") -> None:
		super().__init__(kernel)

		self.layer_bg = self.create_layer()
		self.layer_fg = self.create_layer()

		self.background = self.create_object(self.layer_bg)
		self.background.make_rect(to_rgba_tuple(CNST.BLACK), *self.game.dimensions)
		self.background.opacity = 0
		self.effects.tween(self.background, {"opacity": 153}, 0.4, in_out_quart)

		self.add(TextLine("<PAUSED>", bold=True, x=910, y=650), self.layer_fg)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(Control.ENTER):
			self.remove_scene(end_game=False, reset=False)
		elif self.game.key_handler.just_pressed(Control.BACK):
			self.remove_scene(end_game=True)
