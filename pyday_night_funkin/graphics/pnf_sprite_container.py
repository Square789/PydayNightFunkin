
import typing as t

from pyglet.graphics import Group, get_default_batch

from pyday_night_funkin.graphics.context import Context
from pyday_night_funkin.graphics.pnf_sprite import EffectBound, Movement, PNFSprite

if t.TYPE_CHECKING:
	from pyglet.math import Vec2
	from pyday_night_funkin.graphics.context import Context
	from pyday_night_funkin.types import Numeric

V = t.TypeVar("V")


class PNFSpriteContainer(PNFSprite):
	"""
	Sprite container.
	Tries to be similar to a FlxSpriteGroup by copying the Container
	API, while not inheriting from it, but from PNFSprite instead.
	Yep, this thing breaks the LSP.
	It's important to note that the Container itself should never
	have any sort of graphical representation.
	"""

	def __init__(
		self,
		sprites: t.Sequence[PNFSprite] = (),
		x: "Numeric" = 0,
		y: "Numeric" = 0,
		context: t.Optional[Context] = None,
	) -> None:
		"""
		Initializes a PNFSpriteContainer with all given sprites added
		to it.
		"""

		# NOTE: Copypasted from PNFSprite.__init__, look into it when
		# modifying this!
		self.movement: t.Optional[Movement] = None
		self.effects: t.List["EffectBound"] = []

		self._x = x
		self._y = y
		self._rotation = 0
		self._opacity = 255
		self._rgb = (255, 255, 255)
		self._scale = 1.0
		self._scale_x = 1.0
		self._scale_y = 1.0
		self._scroll_factor = (1.0, 1.0)
		self._visible = True

		self._context = Context(get_default_batch(), Group()) if context is None else context

		self._sprites: t.Set[PNFSprite] = set()
		for spr in sprites:
			self.add(spr)

	def set_context(self, parent_context: "Context") -> None:
		self._context = Context(
			parent_context.batch,
			Group(parent=parent_context.group),
		)
		for x in self._sprites:
			x.set_context(self._context)

	def invalidate_context(self) -> None:
		self.set_context(Context(get_default_batch(), None))

	def add(self, sprite: PNFSprite) -> None:
		sprite.x += self._x
		sprite.y += self._y
		self._sprites.add(sprite)
		sprite.set_context(self._context)

	def remove(self, sprite: PNFSprite) -> None:
		sprite.x -= self._x
		sprite.y -= self._y
		sprite.invalidate_context()
		self._sprites.remove(sprite)

	def delete(self) -> None:
		for x in self._sprites:
			x.delete()
		self._sprites = None
		self._context = None

	def update(self, dt: float) -> None:
		for x in self._sprites:
			x.update(dt)

	def transform_children(self, func: t.Callable[[PNFSprite, V], t.Any], val: V) -> None:
		"""
		# TODO DOCOCOCOOCOCOC
		"""
		for sprite in self._sprites:
			func(sprite, val)

	def screen_center(self, game_dims: "Vec2", x: bool = True, y: bool = True) -> None:
		"""
		Centers all sprites in this SpriteContainer along the given
		axes in respect to the supplied game dimensions.
		"""
		if not self._sprites:
			return

		# NOTE: this may loop over all sprites 6 times when 1 time
		# would be possible too. Don't see any need for extreme over-
		# optimization in that regard for now
		if x:
			max_x = self.max_x
			min_x = self.min_x
			offset = (game_dims[0] - abs(max_x - min_x)) // 2
			for sprite in self._sprites:
				sprite.x = (sprite.x - min_x) + offset
		if y:
			max_y = self.max_y
			min_y = self.min_y
			offset = (game_dims[1] - abs(max_y - min_y)) // 2
			for sprite in self._sprites:
				sprite.y = (sprite.y - min_y) + offset

	@property
	def min_x(self) -> t.Optional["Numeric"]:
		if not self._sprites:
			return None
		return min(sprite.x for sprite in self._sprites)

	@property
	def max_x(self) -> t.Optional["Numeric"]:
		if not self._sprites:
			return None
		return max(sprite.x + sprite.signed_width for sprite in self._sprites)

	@property
	def min_y(self) -> t.Optional["Numeric"]:
		if not self._sprites:
			return None
		return min(sprite.y for sprite in self._sprites)

	@property
	def max_y(self) -> t.Optional["Numeric"]:
		if not self._sprites:
			return None
		return max(sprite.y + sprite.signed_height for sprite in self._sprites)

	def __iter__(self) -> t.Iterator[PNFSprite]:
		yield from self._sprites

	# === PNFSprite property overrides === #

	@staticmethod
	def _transform_x(sprite: PNFSprite, x: "Numeric") -> None:
		sprite.x += x

	@staticmethod
	def _transform_y(sprite: PNFSprite, y: "Numeric") -> None:
		sprite.y += y

	def _set_x(self, x: "Numeric") -> None:
		self.transform_children(self._transform_x, x - self._x)
		self._x = x

	x = property(PNFSprite.x.fget, _set_x)

	def _set_y(self, y: "Numeric") -> None:
		self.transform_children(self._transform_y, y - self._y)
		self._y = y

	y = property(PNFSprite.y.fget, _set_y)
