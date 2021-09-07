
import typing as t

from pyday_night_funkin.levels.week import Week
from pyday_night_funkin.levels.week1level import Bopeebo, Fresh, DadBattle


WEEKS: t.Sequence[Week] = (
	Week(
		"TUTORIAL",
		[
#			LevelBlueprint("Tutorial", Week1Level),
		]
	),
	Week("WEEK 1", [Bopeebo, Fresh, DadBattle]),
)
