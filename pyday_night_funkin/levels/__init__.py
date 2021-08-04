
import typing as t

from pyday_night_funkin.levels.week import Week
from pyday_night_funkin.levels.level import Level, LevelBlueprint
from pyday_night_funkin.levels.week1 import Week1Level


WEEKS: t.Sequence[Week] = (
	Week(
		"TUTORIAL",
		[
			LevelBlueprint("Tutorial", Week1Level),
		]
	),
	Week(
		"WEEK 1",
		[
			LevelBlueprint("Bopeebo", Week1Level),
			LevelBlueprint("Fresh", Week1Level),
			LevelBlueprint("Dad Battle", Week1Level),
		]
	),
)
