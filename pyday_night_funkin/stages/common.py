"""
Contains some functions to create/deliver things that keep appearing
in multiple levels.
"""

import typing as t

from pyday_night_funkin.core.asset_system import load_image
from pyday_night_funkin.note_handler import AbstractNoteHandler, NoteHandler
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.scenes import InGameScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character


class BaseGameBaseStage(InGameScene):
	"""
	Common superclass for the base game's stages.
	Does stuff that happens the same in most stages.
	"""

	@staticmethod
	def get_default_cam_zoom() -> float:
		return 0.9

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return (
			"background0", "background1", "girlfriend", "stage", "curtains",
			("ui_combo", True), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
		)

	def create_hud(self) -> HUD:
		return HUD(self, "hud", "ui", "ui_arrows", ("ui0", "ui1", "ui2"), "ui_combo")

	def create_note_handler(self) -> AbstractNoteHandler:
		return NoteHandler(self, "ui_notes", "hud")

	def create_player(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("stage", "main", char_cls, scene=self, x=770, y=450)

	def create_girlfriend(self, char_cls: t.Type["Character"]) -> "Character":
		gf = self.create_object("girlfriend", "main", char_cls, scene=self, x=400, y=130)
		gf.scroll_factor = (.95, .95)
		return gf

	def setup_default_base_game_arena(self) -> None:
		"""
		Sets up the classic default stage in this scene.
		To be exact:
		- Stageback in layer `background0`
		- Stagefront in layer `background1`
		- Curtains in layer `curtains`
		"""
		stageback = self.create_object(
			"background0", "main", x=-600, y=-200, image=load_image("shared/images/stageback.png")
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.create_object(
			"background1", "main", x=-650, y=600, image=load_image("shared/images/stagefront.png")
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.set_scale_and_repos(1.1)

		stagecurtains = self.create_object(
			"curtains", "main", x=-500, y=-300, image=load_image("shared/images/stagecurtains.png")
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.set_scale_and_repos(.9)
