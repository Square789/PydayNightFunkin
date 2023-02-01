
import typing as t

from pyday_night_funkin.stages.common import BaseGameBaseStage

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character


class TutorialStage(BaseGameBaseStage):
	def setup(self) -> None:
		super().setup()
		self.setup_default_base_game_arena()

	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("girlfriend", "main", char_cls, scene=self, x=400, y=130)
