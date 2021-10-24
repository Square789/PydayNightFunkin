
from dataclasses import dataclass
import typing as t

from pyday_night_funkin.levels.week1level import Bopeebo, Fresh, DadBattle

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGameScene


@dataclass
class Week:
	"""
	Week dataclass containing its name and levels.
	"""
	name: str
	levels: t.Sequence["InGameScene"]

	def __getitem__(self, idx: int) -> "InGameScene":
		return self.levels[idx]


WEEKS: t.Sequence[Week] = (
	Week("TUTORIAL", []),
	Week("WEEK 1", [Bopeebo, Fresh, DadBattle]),
)
