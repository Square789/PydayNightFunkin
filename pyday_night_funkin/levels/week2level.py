

from random import choice, randint
import typing as t

from pyday_night_funkin.characters import Character, Boyfriend, Girlfriend, SkidNPump
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.scenes import InGameScene
from pyday_night_funkin.levels import common

if t.TYPE_CHECKING:
	from pyday_night_funkin.hud import HUD
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class Week2Level(InGameScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self._next_lightning_thresh = 0
		self._last_lightning_beat = 0
		self._lightning_sounds = (
			load_asset(ASSET.SOUND_THUNDER0),
			load_asset(ASSET.SOUND_THUNDER1),
		)

	@staticmethod
	def get_opponent_icon() -> str:
		return "spooky"

	def create_note_handler(self) -> "AbstractNoteHandler":
		return common.create_note_handler(self)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (
			"background", "girlfriend", "stage",
			("ui_combo", True), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
		)

	def create_hud(self) -> "HUD":
		return common.create_hud(self)

	def setup(self) -> None:
		super().setup()

		bg_anims = load_asset(ASSET.XML_HALLOWEEN_BG)
		self.background = self.create_object("background", "main", x=-200, y=-100)
		# The masculine urge to steal the toothbrush of whoever names animations like that
		self.background.animation.add_from_frames("idle", bg_anims["halloweem bg"])
		self.background.animation.add_from_frames(
			"lightning", bg_anims["halloweem bg lightning strike"], 24, False
		)
		self.background.animation.play("idle")

	def create_boyfriend(self) -> "Boyfriend":
		return self.create_object("stage", "main", Boyfriend, scene=self, x=770, y=450)

	def create_girlfriend(self) -> "Girlfriend":
		gf = self.create_object("girlfriend", "main", Girlfriend, scene=self, x=400, y=130)
		gf.scroll_factor = (.95, .95)
		return gf

	def create_opponent(self) -> "Character":
		return self.create_object(
			"stage", "main", object_class=SkidNPump, scene=self, x=100, y=300
		)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		if randint(0, 9) == 0 and self.cur_beat > self._next_lightning_thresh:
			# LIGHTNING BOLT, LIGHTNING BOLT!
			self.sfx_ring.play(choice(self._lightning_sounds))
			self.background.animation.play("lightning")

			self.boyfriend.animation.play("scared", True)
			self.girlfriend.animation.play("scared", True)

			self._next_lightning_thresh = self.cur_beat + randint(8, 24)


class Spookeez(Week2Level):
	@staticmethod
	def get_song() -> str:
		return "spookeez"


class South(Week2Level):
	@staticmethod
	def get_song() -> str:
		return "south"


# Later
# class Monster(Week2Level):
# 	@staticmethod
# 	def get_song() -> str:
# 		return "monster"

# 	@staticmethod
# 	def get_opponent_icon() -> str:
# 		return "monster"
