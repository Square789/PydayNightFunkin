
from loguru import logger
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.asset_system import ASSET, load_asset
from pyday_night_funkin.characters import Boyfriend, DaddyDearest, Girlfriend
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.levels import common
from pyday_night_funkin.note_handler import AbstractNoteHandler, NoteHandler
from pyday_night_funkin.scenes.in_game import InGameScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character, Boyfriend, Girlfriend


class Week1Level(InGameScene):
	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return common.get_layer_names()

	@staticmethod
	def get_default_cam_zoom() -> float:
		return 0.9

	@staticmethod
	def get_opponent_icon() -> str:
		return "dad"

	def create_note_handler(self) -> AbstractNoteHandler:
		return common.create_note_handler(self)

	def create_hud(self) -> HUD:
		return common.create_hud(self)

	def setup(self) -> None:
		super().setup()
		common.setup_default_stage(self)

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
	def get_song() -> str:
		return "bopeebo"

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		if self.cur_beat % 8 == 7:
			self.boyfriend.animation.play("hey")

class Fresh(Week1Level):
	@staticmethod
	def get_song() -> str:
		return "fresh"

class DadBattle(Week1Level):
	@staticmethod
	def get_song() -> str:
		return "dadbattle"
