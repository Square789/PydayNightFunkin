
from enum import IntEnum
import typing as t

from pyglet.image import animation

from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.graphics import PNFSprite
from pyday_night_funkin.graphics.pnf_animation import PNFAnimation, OffsetAnimationFrame


# unused right now
class CHARACTER_STYLE:
	BOLD = 0
	CAPITAL = 1
	LOWERCASE = 2


_ALTS = {
	"#": "hashtag",
	"$": "dollarsign",
	"&": "amp",
	",": "comma",
	"!": "exclamation point",
}

def _map_to_animation(name: str) -> t.Optional[PNFAnimation]:
	if name in _ANIMATIONS:
		return _ANIMATIONS[name]
	if name in _ALTS:
		return _ANIMATIONS[_ALTS[name]]
	if name.isalpha():
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

class AlphabetCharacter(PNFSprite):
	def __init__(self, char: str, *args, **kwargs) -> None:
		self.char = char
		anim = _map_to_animation(char)
		if anim is None:
			raise ValueError(f"Couldn't find alphabet animation for {char!r}!")

		super().__init__(*args, **kwargs)

		self.animation.add("main", anim)
		self.animation.play("main")
		self.check_animation_controller()

