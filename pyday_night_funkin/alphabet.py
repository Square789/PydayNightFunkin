
import typing as t

from pyday_night_funkin.asset_system import ASSET, load_asset
from pyday_night_funkin.core.pnf_animation import PNFAnimation, OffsetAnimationFrame
from pyday_night_funkin.core.pnf_sprite import (
	PNFSprite, PNFSpriteFragmentShader, PNFSpriteVertexShader
)
from pyday_night_funkin.core.pnf_sprite_container import PNFSpriteContainer
from pyday_night_funkin.core.shaders import ShaderContainer
from pyday_night_funkin.utils import lerp

if t.TYPE_CHECKING:
	from pyday_night_funkin.types import Numeric


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

	_ANIMATIONS = None

	@classmethod
	def init_animation_dict(cls):
		"""
		Defer animation dict init to this function as `ASSET` is not
		filled when this module is first imported.
		"""
		cls._ANIMATIONS = {
			prefix: PNFAnimation(
				[
					OffsetAnimationFrame(frame.texture, 1 / 24, frame.frame_info)
					for frame in frames
				],
				loop = True,
			) for prefix, frames in load_asset(ASSET.XML_ALPHABET).items()
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


class TextLine(PNFSpriteContainer):
	"""
	Cheap sprite container subclass that automatically creates
	letter sprites on creation.
	"""
	def __init__(
		cls,
		text: str,
		bold: bool = False,
		color: t.Optional[t.Tuple[int, int, int]] = None,
		x: "Numeric" = 0,
		y: "Numeric" = 0,
		sprite_class: t.Type[AlphabetCharacter] = AlphabetCharacter,
	) -> None:
		"""
		# TODO doc probably
		"""
		sprites = []
		last_sprite = None
		last_was_space = False
		sprite_x = 0
		for c in text:
			if c in " -":
				last_was_space = True
				continue

			if last_sprite:
				sprite_x = last_sprite.x + last_sprite.width
			if last_was_space:
				sprite_x += 40
				last_was_space = False

			sprite = sprite_class(
				x = sprite_x,
				y = 5 * (not c.isalpha()),
				char = c,
				bold = bold,
				color = color,
			)
			last_sprite = sprite
			sprites.append(sprite)

		super().__init__(sprites, x=x, y=y)


class MenuTextLine(TextLine):
	"""
	TextLine subclass that will force itself to a specific
	x and y coordinate.
	"""

	def __init__(self, target_y: int, game_dims: t.Tuple[int, int], *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.target_y = target_y
		self.game_height = game_dims[1]

	def update(self, dt: float) -> None:
		self.x = lerp(self._x, self.target_y * 20 + 90, .16)
		self.y = lerp(self._y, self.target_y * 1.3 * 120 + self.game_height * 0.48, .16)
		super().update(dt)
