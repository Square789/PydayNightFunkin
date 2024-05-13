"""
Defines structures to share content the game can receive and include
in itself.
"""

from dataclasses import dataclass
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import CharacterKernel
	from pyday_night_funkin.scenes.in_game import InGameScene


@dataclass
class LevelData:
	song_name: str
	"""
	The level's song's identifying string.
	Will be used to load it from disk.
	"""

	display_name: str
	"""
	This level's display name, as shown in menus and such.
	Should be free of any special characters that the default
	alphabet can't handle.
	"""

	stage_type: t.Type["InGameScene"]
	"""The InGameScene this level takes place on."""

	player_character: t.Hashable
	"""
	Name of the player controlled character in this level.
	The logic of the `InGameScene` expects the resolved character to
	have the following animations: `{x}_{y}` for x in (`sing`, `miss`)
	and y in (`left`, `down`, `right`, `up`), as well as
	`game_over_{x}` for x in (`ini`, `loop`, `end`). (Unless the
	character specifies a `game_over_fallback` character that does
	have those last animations instead.)
	"""

	girlfriend_character: t.Optional[t.Hashable]
	"""
	Name of the girlfriend, or some kind of background decoration
	bopper of this level. Can be set to `None`, meaning she won't
	appear.
	"""

	opponent_character: t.Hashable
	"""
	Name of the opponent character in this level.
	The opponent sprite is expected to have the following
	animations:
	`sing_{x}` for x in (`left`, `down`, `right`, `up`).
	"""

	libraries: t.Optional[t.Sequence[str]] = ()
	"""
	A collection of libraries whose items should be loaded for this
	level.
	"""


@dataclass
class WeekData:
	"""
	Week dataclass containing a week's name, levels and other things.
	"""

	display_name: str
	"""Name of the week as shown in the story menu and elsewhere."""

	story_menu_chars: t.Tuple[t.Hashable, t.Hashable, t.Hashable]
	"""
	Identifiers of the characters that should appear in this week's story
	menu slot.
	Must be a three-element tuple of character subclasses.
	All sprites are expected to have a `story_menu` animation on them
	and the one at index 1 an additional `story_menu_confirm`
	animation.
	"""

	levels: t.Sequence[LevelData]
	"""
	Levels in this week. Must be a sequence of `LevelData`.
	"""

	header_filename: str
	"""
	File name of this week's header image, to be displayed in the story
	menu.
	"""

	def __getitem__(self, idx: int) -> LevelData:
		return self.levels[idx]


@dataclass
class ContentPack:
	pack_id: t.Hashable
	characters: t.Dict[t.Hashable, "CharacterKernel"]
	weeks: t.Sequence["WeekData"]
