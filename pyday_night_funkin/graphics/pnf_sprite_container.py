
import typing as t
import weakref

from pyglet.graphics import Group

if t.TYPE_CHECKING:
	from pyglet.math import Vec2
	from pyday_night_funkin.types import PNFSpriteBound, Numeric


class Layer():
	"""
	Layer class over the given group.
	"""
	__slots__ = ("group", "force_order", "latest_order")

	def __init__(self, group: Group, force_order: bool) -> None:
		self.group = group
		self.force_order = force_order
		self.latest_order = 0

	def get_group(self, group_cls: t.Type[Group] = Group, *args, **kwargs) -> Group:
		"""
		Returns a group to attach an object to on this layer.

		A layer with forced order will create and return an
		incrementally ordered subgroup with the layer's group as its
		parent.
		A layer without forced order will simply return its own group.
		"""
		# TODO: Not really relevant in practice, but the order will
		# keep increasing ad infinitum, I don't like that a lot
		if self.force_order:
			kwargs["order"] = self.latest_order
			kwargs["parent"] = self.group
			self.latest_order += 1

			return group_cls(*args, **kwargs)
		else:
			return self.group


class PNFSpriteContainer():
	"""
	Sprite container.
	Tries to be similar to a FlxSpriteGroup.
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
