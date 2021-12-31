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

# NOTE: That sucks, but is needed for menu selections etc.
DIFFICULTY_REVERSE_MAP = [DIFFICULTY.EASY, DIFFICULTY.NORMAL, DIFFICULTY.HARD]


class GAME_STATE(IntEnum):
	LOADING = 0
	COUNTDOWN = 1
	PLAYING = 2
	ENDED = 3


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
