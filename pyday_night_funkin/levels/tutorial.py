
import typing as t
from pyday_night_funkin.characters import Boyfriend, Girlfriend, FlipIdleCharacter
from pyday_night_funkin.constants import ERROR_TEXTURE
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.levels import common
from pyday_night_funkin.scenes import InGameScene
from pyday_night_funkin.utils import FrameInfoTexture

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character
	from pyday_night_funkin.note_handler import AbstractNoteHandler


class Tutorial(InGameScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return common.get_layer_names()

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
		not_gf.animation.add_from_frames("idle_left", (FrameInfoTexture(ERROR_TEXTURE, False),))
		not_gf.animation.add_from_frames("idle_right", (FrameInfoTexture(ERROR_TEXTURE, False),))
		not_gf.visible = False
		return not_gf

	def create_opponent(self) -> "Character":
		return self.create_object(
			"girlfriend", "main", object_class=Girlfriend, scene=self, x=400, y=130
		)

	def setup(self) -> None:
		super().setup()
		common.setup_default_stage(self)
