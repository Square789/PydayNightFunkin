
from enum import IntEnum

from pyglet.image import CheckerImagePattern, Texture


PINK =  (0xFF, 0x00, 0xFF, 0xFF)
BLACK = (0x00, 0x00, 0x00, 0xFF)
WHITE = (0xFF, 0xFF, 0xFF, 0xFF)
RED =   (0xAA, 0x00, 0x00, 0xFF)

GAME_WIDTH, GAME_HEIGHT = GAME_DIMENSIONS = (1280, 720)

STATIC_ARROW_Y = 50

ERROR_TEXTURE = CheckerImagePattern(PINK, BLACK).create_image(32, 32).create_texture(Texture)

SFX_RING_SIZE = 8

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
