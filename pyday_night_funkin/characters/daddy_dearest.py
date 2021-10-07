
import typing as t

from pyday_night_funkin.characters._base import Character
from pyday_night_funkin.asset_system import ASSETS, load_asset

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class DaddyDearest(Character):

	# Idk why but if the original game says so
	hold_timeout = 6.1

	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(scene, *args, **kwargs)
		anims = load_asset(ASSETS.XML.DADDY_DEAREST)
		self.animation.add("idle_bop", anims["Dad idle dance"], 24, True)
		self.animation.add("sing_note_left", anims["Dad Sing Note LEFT"], 24, False, (-10, 10))
		self.animation.add("sing_note_down", anims["Dad Sing Note DOWN"], 24, False, (0, -30))
		self.animation.add("sing_note_up", anims["Dad Sing Note UP"], 24, False, (-6, 50))
		self.animation.add("sing_note_right", anims["Dad Sing Note RIGHT"], 24, False, (0, 27))
