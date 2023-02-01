"""
Defines structures to share content the game can receive and include
in itself.
"""
# Should become the gateway to mods soon, maybe.

from dataclasses import dataclass
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character
	from pyday_night_funkin.scenes.in_game import InGameScene


@dataclass
class LevelData:
	song_name: str
	"""
	The level's song's identifying string.
	A call to `load_song(song_name, ...)` will be made eventually.
	"""

	display_name: str
	"""
	This level's display name, as shown in menus and such.
	Should be free of any special characters that the default
	alphabet can't handle.
	"""

	stage_class: t.Type["InGameScene"]
	"""The InGameScene this level takes place on."""

	player_character: t.Hashable
	"""Name of the player controlled character in this level."""

	girlfriend_character: t.Optional[t.Hashable]
	"""
	Name of the girlfriend of this level. Can be set to `None`,
	meaning she won't appear.
	"""

	opponent_character: t.Hashable
	"""Name of the opponent character in this level."""


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

	def __getitem__(self, idx: int) -> t.Hashable:
		return self.levels[idx]


@dataclass
class ContentPack:
	pack_id: t.Hashable
	characters: t.Dict[t.Hashable, t.Type["Character"]]
	weeks: t.Sequence["WeekData"]
