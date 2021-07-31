
import typing as t

from pyday_night_funkin.levels.week import Week
from pyday_night_funkin.levels.level import Level, LevelBlueprint
from pyday_night_funkin.levels.week1 import Week1Level


WEEKS: t.Sequence[Week] = (
	Week(
		"TUTORIAL",
		[
			LevelBlueprint(
				"Tutorial",
				"songs/test",
				Week1Level
			),
		]
	),
	Week(
		"WEEK 1",
		[
			LevelBlueprint(
				"Bopeebo",
				"songs/test",
				Week1Level
			),
			LevelBlueprint(
				"Fresh",
				"songs/test",
				Week1Level
			),
			LevelBlueprint(
				"Dad Battle",
				"songs/test",
				Week1Level
			),
		]
	),
)
