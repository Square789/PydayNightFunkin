import typing as t

from pyday_night_funkin.enums import CONTROL
from pyday_night_funkin.scenes import MusicBeatScene, MainMenuScene

from pyday_night_funkin.core.pnf_text import PNFText

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.scene import SceneKernel


class SettingsScene(MusicBeatScene):
	def __init__(self, kernel: "SceneKernel") -> None:
		super().__init__(kernel)
		text = PNFText(
			text = "Under construction. Press back to go back.",
			font_size = 24,
			font_name = "VCR OSD Mono",
		)
		text.screen_center((self.default_camera._width, self.default_camera._height))
		self.add(text)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.BACK):
			self.game.set_scene(MainMenuScene)
