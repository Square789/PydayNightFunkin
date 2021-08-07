
from dataclasses import dataclass
import typing as t

from pyday_night_funkin.asset_system import SONGS

if t.TYPE_CHECKING:
	from pyglet.media import Source
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

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ()

	@staticmethod
	def get_layer_names() -> t.Sequence[str]:
		return ()

	def load_resources(self) -> None:
		"""
		This function will be called by the game scene in an early
		state of level setup # TODO DOC. Override it in a subclass!
		"""
		pass

	def load_song(self) -> t.Tuple["Source", t.Optional["Source"], t.Dict[str, t.Any]]:
		"""
		Loads a song's data as a three-tuple. The first two elements
		are the instrumental and vocal tracks as two static sources.
		The vocals may be `None`. The third element is the song's full
		json data.
		Override this function if you want to modify the songs in some
		way or load them as streaming sources instead.
		"""
		return SONGS[self.info.name].load((False, False), self.game_scene.info.difficulty)

	def on_start(self) -> None:
		pass


@dataclass
class LevelBlueprint:
	"""
	A level blueprint contains a level's name and a concrete level
	class to be instantiated in an `InGame` scene.
	Purpose of this is to delay actual level creation to (A) only when
	they are needed and (B) if an `InGame` scene to create them under
	exists.
	"""
	name: str
	class_: t.Type[Level]

	def create_level(self, game_scene: "InGame") -> Level:
		return self.class_(self, game_scene)
