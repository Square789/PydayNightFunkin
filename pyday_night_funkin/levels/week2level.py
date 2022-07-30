

from random import choice, randint
import typing as t

from pyday_night_funkin.base_game_pack import (
	Boyfriend, Girlfriend, SkidNPump, Monster, load_frames
)
from pyday_night_funkin.core.asset_system import load_sound
from pyday_night_funkin.scenes import InGameScene
from pyday_night_funkin.levels import common

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character
	from pyday_night_funkin.hud import HUD
	from pyday_night_funkin.note_handler import AbstractNoteHandler


MonsterChar = Monster # yikes


class Week2Level(InGameScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self._next_lightning_thresh = 0
		self._lightning_sounds = (
			load_sound("shared/sounds/thunder_1.ogg"),
			load_sound("shared/sounds/thunder_2.ogg"),
		)

	@staticmethod
	def get_opponent_icon() -> str:
		return "spooky"

	def create_note_handler(self) -> "AbstractNoteHandler":
		return common.create_note_handler(self)

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (
			"background", "girlfriend", "stage",
			("ui_combo", True), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
		)

	def create_hud(self) -> "HUD":
		return common.create_hud(self)

	def setup(self) -> None:
		super().setup()

		self.background = self.create_object("background", "main", x=-200, y=-100)
		self.background.frames = load_frames("week2/images/halloween_bg.xml")
		# The masculine urge to steal the toothbrush of whoever names animations like that
		self.background.animation.add_by_prefix("idle", "halloweem bg0")
		self.background.animation.add_by_prefix(
			"lightning", "halloweem bg lightning strike", 24, False
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
			"stage", "main", SkidNPump, scene=self, x=100, y=300
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


class Monster(Week2Level):
	@staticmethod
	def get_song() -> str:
		return "monster"

	@staticmethod
	def get_opponent_icon() -> str:
		return "monster"

	def create_opponent(self) -> "Character":
		return self.create_object("stage", "main", MonsterChar, scene=self, x=100, y=230)
