
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.graphics import PNFSprite
from pyday_night_funkin.graphics.pnf_animation import PNFAnimation, OffsetAnimationFrame
from pyday_night_funkin.graphics.pnf_sprite_container import PNFSpriteContainer
from pyday_night_funkin.graphics.shaders import (
	PNFSpriteFragmentShader, PNFSpriteVertexShader, ShaderContainer
)

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import BaseScene


def create_text_line(
	text: str,
	scene: "BaseScene",
	layer: str,
	camera: t.Optional[str] = None,
	bold: bool = False,
	color: t.Optional[t.Tuple[int, int, int]] = None,
	x: float = 0,
	y: float = 0,
) -> PNFSpriteContainer:
	"""
	Very cheap text layout function designed to work with the
	scenes.
	"""
	# This sucks
	container = PNFSpriteContainer()
	last_sprite = None
	last_was_space = False
	x_pos = x
	for c in text:
		if c in " -":
			last_was_space = True
			continue

		if last_sprite:
			x_pos = last_sprite.x + last_sprite.width
		if last_was_space:
			x_pos += 40
			last_was_space = False

		sprite = scene.create_sprite(
			layer,
			camera,
			AlphabetCharacter,
			x = x_pos,
			y = y + (5 * (not c.isalpha())),
			char = c,
			bold = bold,
			color = color,
		)
		last_sprite = sprite
		container.add(sprite)

	return container



_COLOR_SET_SHADER_CONTAINER = ShaderContainer(
	PNFSpriteVertexShader.generate(),
	PNFSpriteFragmentShader.generate(0.01, PNFSpriteFragmentShader.COLOR.SET),
)

class AlphabetCharacter(PNFSprite):
	"""
	Sprite subclass for an alphabet character handling
	character->animation translation.
	In the default game's alphabet, most symbols are an all-black
	monochromatic shape, which is why this class does some funky
	shader things to allow for their recoloration (see `__init__` doc).
	"""

	_ALTS = {
		"#": "hashtag",
		"$": "dollarsign",
		"&": "amp",
		",": "comma",
		"!": "exclamation point",
		"'": "apostraphie", # the spelling bee is dead and you killed it
		"/": "forward slash",
		".": "period",
		"?": "question mark",

	}

	_ANIMATIONS = {
		prefix: PNFAnimation(
			[
				OffsetAnimationFrame(frame.texture, 1 / 24, frame.frame_info)
				for frame in frames
			],
			loop = True,
		) for prefix, frames in load_asset(ASSETS.XML.ALPHABET).items()
	}

	def _get_animation(self) -> t.Optional[PNFAnimation]:
		name = self.char
		bold = self.bold
		_ANIMATIONS = self._ANIMATIONS
		_ALTS = self._ALTS

		if name in _ANIMATIONS:
			return _ANIMATIONS[name]
		if name in _ALTS:
			return _ANIMATIONS[_ALTS[name]]
		if name.isalpha():
			if bold:
				return _ANIMATIONS[f"{name.upper()} bold"]
			else:
				return _ANIMATIONS[f"{name} {'lowercase' if name.islower() else 'capital'}"]
		return None

	def __init__(
		self,
		char: str,
		bold: bool = False,
		color: t.Optional[t.Tuple[int, int, int]] = None,
		*args,
		**kwargs,
	) -> None:
		"""
		Initialize a character for the given `char`.
		If `bold` is set to `True`, an uppercase bold alt will be used
		for ONLY letters.
		If `color` is given as a three-integer tuple and the chosen
		animation is *not* a bold one (this may still happen if `bold`
		is True, but the `char` is not a letter), instead of the
		default shader, which blends a texture's color with the sprite
		color, a shader that sets the sprite color, ignoring the texture
		color in all channels except for alpha, will be put in place
		and the color applied to the sprite immediatedly.
		This way it's possible to color the entire letter in any desired
		color. If `color` is left at `None`, the alternative shader will
		not be set and the character remain as usual.
		"""
		self.char = char
		self.bold = bold

		should_color = color is not None and (not bold or not self.char.isalpha())
		if should_color:
			self.shader_container = _COLOR_SET_SHADER_CONTAINER

		super().__init__(*args, **kwargs)
		if should_color:
			self.color = color

		if (anim := self._get_animation()) is None:
			raise ValueError(f"Couldn't find alphabet animation for {char!r}!")

		self.animation.add("main", anim)
		self.animation.play("main")
		self.check_animation_controller()
