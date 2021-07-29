
from dataclasses import dataclass
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.levels import LevelBlueprint


@dataclass
class Week:
	"""
	Week dataclass containing its name and levels.
	"""
	name: str
	levels: t.Sequence["LevelBlueprint"]

	def __getitem__(self, idx: int) -> "LevelBlueprint":
		return self.levels[idx]
