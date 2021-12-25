
from dataclasses import dataclass
import typing as t

from pyday_night_funkin import characters as chars
from pyday_night_funkin.levels.tutorial import Tutorial
from pyday_night_funkin.levels.week1level import Bopeebo, Fresh, DadBattle

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character
	from pyday_night_funkin.scenes import InGameScene


@dataclass
class Week:
	"""
	Week dataclass containing a week's name, levels and other things.
	"""

	name: str
	"""Name of the week."""

	story_menu_chars: t.Tuple[t.Type["Character"], t.Type["Character"], t.Type["Character"]]
	"""
	Characters that should appear in this week's story menu slot.
	Must be a three-element tuple of character subclasses.
	All sprites are expected to have a `story_menu` animation on them
	and the one at index 1 an additional `story_menu_confirm`
	animation.
	"""

	levels: t.Sequence[t.Type["InGameScene"]]
	"""
	Levels in this week. Must be a sequence of `InGameScene` classes.
	"""

	def __getitem__(self, idx: int) -> t.Type["InGameScene"]:
		return self.levels[idx]


WEEKS: t.Sequence[Week] = (
	Week(
		"TUTORIAL",
		(chars.DaddyDearest, chars.Boyfriend, chars.Girlfriend),
		(Tutorial,),
	),
	Week(
		"WEEK 1",
		(chars.DaddyDearest, chars.Boyfriend, chars.Girlfriend),
		(Bopeebo, Fresh, DadBattle),
	),
)
