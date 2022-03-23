
import sys

from pyglet.image import CheckerImagePattern, Texture, ImageData


ADDRESS_PADDING = (sys.maxsize.bit_length() + 1) // 4

ERROR_TEXTURE = CheckerImagePattern(
	(0xFF, 0x00, 0xFF, 0xFF), (0x00, 0x00, 0x00, 0xFF)
).create_image(32, 32).create_texture(Texture)

PIXEL_TEXTURE = ImageData(1, 1, "RGBA", b"\xFF\xFF\xFF\xFF").get_texture()

SFX_RING_SIZE = 4

MAX_ALPHA_SSBO_BINDING_IDX = 0
