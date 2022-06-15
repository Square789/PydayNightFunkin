
import sys

from pyglet.image import CheckerImagePattern, Texture, ImageData


ADDRESS_PADDING = (sys.maxsize.bit_length() + 1) // 4

ERROR_TEXTURE: Texture = CheckerImagePattern(
	(0xFF, 0x00, 0xFF, 0xFF),
	(0x00, 0x00, 0x00, 0xFF)
).create_image(16, 16).create_texture(Texture)

PIXEL_TEXTURE: Texture = ImageData(1, 1, "RGBA", b"\xFF\xFF\xFF\xFF").get_texture()

SFX_RING_SIZE = 4
