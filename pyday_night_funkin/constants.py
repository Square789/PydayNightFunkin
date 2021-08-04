
from pyglet.image import CheckerImagePattern, Texture


PINK =  (0xFF, 0x00, 0xFF, 0xFF)
BLACK = (0x00, 0x00, 0x00, 0xFF)
WHITE = (0xFF, 0xFF, 0xFF, 0xFF)
RED =   (0xAA, 0x00, 0x00, 0xFF)

GAME_WIDTH, GAME_HEIGHT = GAME_DIMENSIONS = (1280, 720)

ERROR_TEXTURE = CheckerImagePattern(PINK, BLACK).create_image(32, 32).create_texture(Texture)

