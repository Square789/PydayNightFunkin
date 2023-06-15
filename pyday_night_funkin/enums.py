"""
Enums that aren't really too coupled to anything else.
"""

from enum import IntEnum


class Difficulty(IntEnum):
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


class Control(IntEnum):
	LEFT = 0
	DOWN = 1
	UP = 2
	RIGHT = 3
	ENTER = 4
	BACK = 5
	VOLUME_UP = 100
	VOLUME_DOWN = 101
	DEBUG_DESYNC = 1000
	DEBUG_WIN = 1001
	DEBUG_LOSE = 1002


class AnimationTag(IntEnum):
	IDLE = 0
	SING = 1
	MISS = 2
	SPECIAL = 3
	STATIC = 4
	PRESSED = 5
	CONFIRM = 6
	HAIR = 7
