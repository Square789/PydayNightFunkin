
from pyglet.image import CheckerImagePattern, Texture

from pyday_night_funkin.utils import to_rgba_tuple

PINK =  0xFF00FFFF
BLACK = 0x000000FF
WHITE = 0xFFFFFFFF
RED =   0xAA0000FF

GAME_WIDTH, GAME_HEIGHT = GAME_DIMENSIONS = (1280, 720)

STATIC_ARROW_Y = 50

ERROR_TEXTURE = CheckerImagePattern(
	to_rgba_tuple(PINK), to_rgba_tuple(BLACK)
).create_image(32, 32).create_texture(Texture)

SFX_RING_SIZE = 4
