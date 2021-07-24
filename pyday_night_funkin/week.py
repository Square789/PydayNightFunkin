
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

	def __init__(self, name: str) -> None:
		self.name = name

	def get_layer_names(self) -> t.Sequence[str]:
		return ()

	def load_sprites(self, game_scene: "InGame") -> None:
		"""
		This function will be called by the game scene in an early
		state of level setup # TODO DOC. Override it in a subclass!
		"""
		pass

	def on_start(self) -> None:
		pass


@dataclass
class Week:
	"""
	Week dataclass containing its name and levels.
	"""
	name: str
	levels: t.Sequence[Level]
