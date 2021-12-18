
from dataclasses import dataclass
import typing as t

from pyday_night_funkin.levels.tutorial import Tutorial
from pyday_night_funkin.levels.week1level import Bopeebo, Fresh, DadBattle

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGameScene


@dataclass
class Week:
	"""
	Week dataclass containing a week's name, levels and other things.
	"""
	name: str
	story_menu_chars: t.Tuple[str, str, str]
	levels: t.Sequence["InGameScene"]

	def __getitem__(self, idx: int) -> "InGameScene":
		return self.levels[idx]


WEEKS: t.Sequence[Week] = (
	Week("TUTORIAL", ("dad", "bf", "gf"), (Tutorial, )),
	Week("WEEK 1",   ("dad", "bf", "gf"), (Bopeebo, Fresh, DadBattle)),
)
