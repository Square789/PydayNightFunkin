from pyday_night_funkin.enums import CONTROL
from pyday_night_funkin.scenes import MusicBeatScene, MainMenuScene

from pyday_night_funkin.core.pnf_text import PNFText


class SettingsScene(MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		text = PNFText(
			48,
			48,
			"Under construction. Press back to go back.",
			24,
			"VCR OSD Mono",
			multiline = True,
			width = 600,
		)
		self.add(text)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler[CONTROL.BACK]:
			self.game.set_scene(MainMenuScene)
