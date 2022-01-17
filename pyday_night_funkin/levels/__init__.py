
from dataclasses import dataclass
import typing as t

from pyday_night_funkin import characters as chr
from pyday_night_funkin.levels.tutorial import Tutorial
from pyday_night_funkin.levels.week1level import Bopeebo, Fresh, DadBattle
from pyday_night_funkin.levels.week2level import Spookeez, South

if t.TYPE_CHECKING:
	from pyday_night_funkin.characters import Character
	from pyday_night_funkin.scenes import InGameScene


@dataclass
class Week:
	"""
	Week dataclass containing a week's name, levels and other things.
	"""

	display_name: str
	"""Name of the week as shown in the story menu and elsewhere."""

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

	header_filename: str
	"""
	File name of this week's header image, to be displayed in the story
	menu.
	"""

	def __getitem__(self, idx: int) -> t.Type["InGameScene"]:
		return self.levels[idx]


WEEKS: t.Sequence[Week] = (
	Week(
		"",
		(chr.DaddyDearest, chr.Boyfriend, chr.Girlfriend),
		(Tutorial,),
		"week0.png",
	),
	Week(
		"DADDY DEAREST",
		(chr.DaddyDearest, chr.Boyfriend, chr.Girlfriend),
		(Bopeebo, Fresh, DadBattle),
		"week1.png",
	),
	Week(
		"SPOOKY MONTH",
		(chr.SkidNPump, chr.Boyfriend, chr.Girlfriend),
		(Spookeez, South),
		"week2.png",
	)
)
