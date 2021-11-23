
import typing as t

from pyglet.image import TextureRegion

from pyday_night_funkin.asset_system import ASSETS, load_asset


class IconGrid():
	def __init__(self) -> None:
		self.icons = None

	def ensure(self) -> None:
		if self.icons is not None:
			return

		img = load_asset(ASSETS.IMG.ICON_GRID)

		if img.width < 1500 or img.height < 900:
			raise ValueError("Icon grid has invalid shape!")

		self.icons = {}
		for name, coords in (
			("bf",                ((   0,   0), ( 150,   0))),
			("spooky",            (( 300,   0), ( 450,   0))),
			("pico",              (( 600,   0), ( 750,   0))),
			("mom",               (( 900,   0), (1050,   0))),
			("tankman",           ((1200,   0), (1350,   0))),
			("face",              ((   0, 150), ( 150, 150))),
			("dad",               (( 300, 150), ( 450, 150))),
			("bf-old",            (( 600, 150), ( 750, 150))),
			("gf",                (( 900, 150), ( 900, 150))),
			("parents-christmas", ((1050, 150), (1200, 150))),
			("monster",           ((1350, 150), (   0, 300))),
			("bf-pixel",          (( 150, 300), ( 150, 300))),
			("senpai",            (( 300, 300), ( 300, 300))),
			("spirit",            (( 450, 300), ( 456, 300))),
		):
			self.icons[name] = tuple(
				img.get_region(x, img.height - 150 - y, 150, 150).get_texture()
				for x, y in coords
			)


_ig = IconGrid()

def get(name: str) -> t.Tuple[TextureRegion, TextureRegion]:
	"""
	Returns a two-tuple with the normal and losing icon for the given
	character, or raises KeyError if the character is unknown.
	"""
	_ig.ensure()
	return _ig.icons[name]
