
from dataclasses import dataclass
import typing as t

from pyday_night_funkin.levels.week import Week
from pyday_night_funkin.levels.level import Level
from pyday_night_funkin.levels.week1level import Bopeebo, Fresh, DadBattle

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame


WEEKS: t.Sequence[Week] = (
	Week(
		"TUTORIAL",
		[
#			LevelBlueprint("Tutorial", Week1Level),
		]
	),
	Week("WEEK 1", [Bopeebo, Fresh, DadBattle]),
)
