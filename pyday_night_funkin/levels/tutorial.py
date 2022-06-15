
import typing as t

from pyday_night_funkin.base_game_pack import Boyfriend, Girlfriend, FlipIdleCharacter
from pyday_night_funkin.core.animation import Animation
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.levels import common
from pyday_night_funkin.scenes import InGameScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class Tutorial(InGameScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return common.get_default_layers()

	@staticmethod
	def get_opponent_icon() -> str:
		return "gf"

	@staticmethod
	def get_song() -> str:
		return "tutorial"

	def create_note_handler(self) -> "AbstractNoteHandler":
		return common.create_note_handler(self)

	def create_hud(self) -> HUD:
		return common.create_hud(self)

	def create_boyfriend(self) -> "Boyfriend":
		return self.create_object("stage", "main", Boyfriend, scene=self, x=770, y=450)

	def create_girlfriend(self) -> "Girlfriend":
		not_gf = self.create_object(
			"girlfriend", "main", object_class=FlipIdleCharacter, scene=self, x=-100, y=-100
		)
		# Epic fail if no dummy animations are added
		not_gf.animation.add("idle_left", (Animation([0])))
		not_gf.animation.add("idle_right", (Animation([0])))
		not_gf.visible = False
		return not_gf

	def create_opponent(self) -> "Character":
		return self.create_object(
			"girlfriend", "main", object_class=Girlfriend, scene=self, x=400, y=130
		)

	def setup(self) -> None:
		super().setup()
		common.setup_default_stage(self)
