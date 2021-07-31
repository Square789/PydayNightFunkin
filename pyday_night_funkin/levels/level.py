
from dataclasses import dataclass
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame

class Level:
	"""
	Class to contain everything relating to a level.
	This includes scenery asset paths, the song files, the selected
	difficulty and even extendable functions to render and handle
	level-specific events.
	This class does not result in a proper level. For
	customization, subclass it (see existing weeks for examples).
	"""

	def __init__(self, info: "LevelBlueprint", game_scene: "InGame") -> None:
		self.info = info
		self.game_scene = game_scene

	def get_camera_names(self) -> t.Sequence[str]:
		return ()

	def get_layer_names(self) -> t.Sequence[str]:
		return ()

	def load_sprites(self) -> None:
		"""
		This function will be called by the game scene in an early
		state of level setup # TODO DOC. Override it in a subclass!
		"""
		pass

	def load_ui(self) -> None:
		pass

	def on_start(self) -> None:
		pass

@dataclass
class LevelBlueprint:
	name: str
	song_dir: str
	class_: t.Type[Level]

	def create_level(self, game_scene: "InGame") -> Level:
		return self.class_(self, game_scene)
