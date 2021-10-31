
from loguru import logger
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.characters import Boyfriend, DaddyDearest, Girlfriend
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.note_handler import AbstractNoteHandler, NoteHandler
from pyday_night_funkin.scenes.in_game import InGameScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character, Boyfriend, Girlfriend


class Week1Level(InGameScene):
	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (
			"background0", "background1", "girlfriend", "stage", "curtains",
			("ui_combo", True), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
		)
		# TODO: change health bar, creating 3 layers for it like this seems really wrong
		# countdown sprites on ui0

	@staticmethod
	def get_default_cam_zoom() -> float:
		return 0.9

	@staticmethod
	def get_opponent_icon() -> str:
		return "dad"

	def create_note_handler(self) -> AbstractNoteHandler:
		return NoteHandler(self, "ui_notes", "hud")

	def create_hud(self) -> HUD:
		return HUD(self, "hud", "ui", "ui_arrows", ("ui0", "ui1", "ui2"), "ui_combo")

	def setup(self) -> None:
		super().setup()

		stageback = self.create_sprite(
			"background0", "main", x=-600, y=-200, image=load_asset(ASSETS.IMG.STAGE_BACK)
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.create_sprite(
			"background1", "main", x=-650, y=600, image=load_asset(ASSETS.IMG.STAGE_FRONT)
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.scale = 1.1

		stagecurtains = self.create_sprite(
			"curtains", "main", x=-500, y=-300, image=load_asset(ASSETS.IMG.STAGE_CURTAINS)
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.scale = 0.9

	def create_boyfriend(self) -> "Boyfriend":
		return self.create_sprite("stage", "main", Boyfriend, scene=self, x=770, y=450)

	def create_girlfriend(self) -> "Girlfriend":
		gf = self.create_sprite("girlfriend", "main", Girlfriend, scene=self, x=400, y=130)
		gf.scroll_factor = (.95, .95)
		return gf

	def create_opponent(self) -> "Character":
		return self.create_sprite("stage", "main", DaddyDearest, scene=self, x=100, y=100)

class Bopeebo(Week1Level):
	@staticmethod
	def get_song() -> int:
		return ASSETS.SONG.BOPEEBO

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.cur_beat % 8 == 7:
			self.boyfriend.animation.play("hey")

class Fresh(Week1Level):
	@staticmethod
	def get_song() -> int:
		return ASSETS.SONG.FRESH

class DadBattle(Week1Level):
	@staticmethod
	def get_song() -> int:
		return ASSETS.SONG.DAD_BATTLE
