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


class GAME_STATE(IntEnum):
	LOADING = 0
	START_DIALOGUE = 1
	COUNTDOWN = 2
	PLAYING = 3
	END_DIALOGUE = 4


class ANIMATION_TAG(IntEnum):
	STATIC = 0
	PRESSED = 1
	CONFIRM = 2

	IDLE = 0
	SING = 1
	MISS = 2
	SPECIAL = 3
