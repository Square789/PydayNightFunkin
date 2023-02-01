"""
Enums that aren't really too coupled to anything else.
"""

from enum import IntEnum


class DIFFICULTY(IntEnum):
	EASY = 0
	NORMAL = 1
	HARD = 2

	def to_song_json_suffix(self) -> str:
		if self is self.EASY:
			return "-easy"
		elif self is self.NORMAL:
			return ""
		elif self is self.HARD:
			return "-hard"
		return ""

	def to_atlas_prefix(self) -> str:
		if self is self.EASY:
			return "EASY"
		elif self is self.NORMAL:
			return "NORMAL"
		elif self is self.HARD:
			return "HARD"
		return ""


class CONTROL(IntEnum):
	LEFT = 0
	DOWN = 1
	UP = 2
	RIGHT = 3
	ENTER = 4
	BACK = 5
	DEBUG_DESYNC = 100
	DEBUG_WIN = 101
	DEBUG_LOSE = 102


class ANIMATION_TAG(IntEnum):
	IDLE = 0
	SING = 1
	MISS = 2
	SPECIAL = 3
	STORY_MENU = 4
	STATIC = 5
	PRESSED = 6
	CONFIRM = 7
	GAME_OVER = 8
	HAIR = 9
