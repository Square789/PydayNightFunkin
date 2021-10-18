
import typing as t

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.graphics import PNFSprite
from pyday_night_funkin.graphics.pnf_animation import PNFAnimation, OffsetAnimationFrame

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import BaseScene


_ALTS = {
	"#": "hashtag",
	"$": "dollarsign",
	"&": "amp",
	",": "comma",
	"!": "exclamation point",
}

def _map_to_animation(name: str, bold: bool) -> t.Optional[PNFAnimation]:
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

_ANIMATIONS = {
	prefix: PNFAnimation(
		[
			OffsetAnimationFrame(frame.texture, 1 / 24, frame.frame_info)
			for frame in frames
		],
		loop = True,
	) for prefix, frames in load_asset(ASSETS.XML.ALPHABET).items()
}


def create_text_line(
	text: str,
	scene: "BaseScene",
	layer: str,
	camera: t.Optional[str] = None,
	bold: bool = False,
	x: float = 0,
	y: float = 0,
) -> None:
	"""
	Very cheap text layout function designed to work with the
	scenes.
	"""
	# NOTE: This sucks
	sprites = []
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
			y = y,
			char = c,
			bold = bold,
		)
		last_sprite = sprite
		sprites.append(sprite)

	return sprites


class AlphabetCharacter(PNFSprite):
	def __init__(self, char: str, bold: bool = False, *args, **kwargs) -> None:
		self.char = char
		anim = _map_to_animation(char, bold)
		if anim is None:
			raise ValueError(f"Couldn't find alphabet animation for {char!r}!")

		super().__init__(*args, **kwargs)

		self.animation.add("main", anim)
		self.animation.play("main")
		self.check_animation_controller()

