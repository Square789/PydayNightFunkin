
import typing as t
import weakref

if t.TYPE_CHECKING:
	from pyglet.math import Vec2
	from pyday_night_funkin.types import PNFSpriteBound, Numeric


class PNFSpriteContainer():
	"""
	Util for applying operations to multiple sprites.
	"""

	def __init__(self, sprites: t.Sequence["PNFSpriteBound"] = ()) -> None:
		self.sprites = weakref.WeakSet(sprites)

	def add(self, sprite: "PNFSpriteBound") -> None:
		self.sprites.add(sprite)

	def remove(self, sprite: "PNFSpriteBound") -> None:
		self.sprites.remove(sprite)

	def discard(self, sprite: "PNFSpriteBound") -> None:
		self.sprites.discard(sprite)

	def screen_center(self, game_dims: "Vec2", x: bool = True, y: bool = True) -> None:
		"""
		Centers all sprites in this SpriteContainer along the given
		axes in respect to the supplied game dimensions.
		"""
		if not self.sprites:
			return

		# NOTE: this may loop over all sprites 6 times when 1 time
		# would be possible too. Don't see any need for extreme over-
		# optimization in that regard for now
		if x:
			max_x = self.max_x
			min_x = self.min_x
			offset = (game_dims[0] - abs(max_x - min_x)) // 2
			for sprite in self.sprites:
				sprite.x = (sprite.x - min_x) + offset
		if y:
			max_y = self.max_y
			min_y = self.min_y
			offset = (game_dims[1] - abs(max_y - min_y)) // 2
			for sprite in self.sprites:
				sprite.y = (sprite.y - min_y) + offset

	@property
	def min_x(self) -> t.Optional["Numeric"]:
		if not self.sprites:
			return None
		return min(sprite.x for sprite in self.sprites)

	@property
	def max_x(self) -> t.Optional["Numeric"]:
		if not self.sprites:
			return None
		return max(sprite.x + sprite.signed_width for sprite in self.sprites)

	@property
	def min_y(self) -> t.Optional["Numeric"]:
		if not self.sprites:
			return None
		return min(sprite.y for sprite in self.sprites)

	@property
	def max_y(self) -> t.Optional["Numeric"]:
		if not self.sprites:
			return None
		return max(sprite.y + sprite.signed_height for sprite in self.sprites)

	def __iter__(self) -> t.Iterator["PNFSpriteBound"]:
		yield from self.sprites
