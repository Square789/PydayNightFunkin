
import typing as t

from pyday_night_funkin.core.graphics import PNFGroup
from pyday_night_funkin.core.pnf_sprite import EffectBound, Movement, PNFSprite
from pyday_night_funkin.core.scene_context import SceneContext
from pyday_night_funkin.core.scene_object import WorldObject
from pyday_night_funkin.core.tweens import TWEEN_ATTR
from pyday_night_funkin.core.utils import clamp

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.types import Numeric

V = t.TypeVar("V")


class PNFSpriteContainer(PNFSprite):
	"""
	Sprite container.
	Tries to be similar to a FlxSpriteGroup by copying the Container
	API, while not inheriting from it, but from PNFSprite instead.
	Yep, this thing breaks the LSP.
	It's important to note that the Container itself should never
	have any sort of graphical representation, does not own an
	interfacer and any sort of attempt to interact with one will
	result in AttributeErrors.
	"""

	_TWEEN_ATTR_NAME_MAP = {
		TWEEN_ATTR.X: "x",
		TWEEN_ATTR.Y: "y",
		TWEEN_ATTR.OPACITY: "opacity",
	}

	def __init__(
		self,
		sprites: t.Sequence[PNFSprite] = (),
		x: "Numeric" = 0,
		y: "Numeric" = 0,
		context: t.Optional[SceneContext] = None,
	) -> None:
		"""
		Initializes a PNFSpriteContainer with all given sprites added
		to it.
		"""

		# NOTE: Copypasted from PNFSprite.__init__, look into it when
		# modifying this!
		self.movement: t.Optional[Movement] = None
		self.effects: t.List["EffectBound"] = []

		WorldObject.__init__(self, x, y)
		self._opacity = 255
		self._color = (255, 255, 255)

		self._context = context or SceneContext()

		self._sprites: t.Set[PNFSprite] = set()
		for spr in sprites:
			self.add(spr)

	def set_context(self, parent_context: SceneContext) -> None:
		self._context.batch = parent_context.batch
		self._context.group = PNFGroup(parent_context.group)
		self._context.cameras = parent_context.cameras
		for x in self._sprites:
			x.set_context(self._context)

	def add(self, sprite: PNFSprite) -> None:
		"""
		Adds a sprite to this sprite container. Will modify the
		sprite's position, so in a way it now belongs to this
		container.
		"""
		sprite.position = (sprite.x + self._x, sprite.y + self._y)
		self._sprites.add(sprite)
		sprite.set_context(self._context)

	def remove(self, sprite: PNFSprite) -> None:
		"""
		Removes a sprite from this sprite container.
		"""
		sprite.position = (sprite.x - self._x, sprite.y - self._y)
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
		Applies a function taking a sprite and a single parameter of
		any type to each sprite with the given parameter.
		"""
		for sprite in self._sprites:
			func(sprite, val)

	def __iter__(self) -> t.Iterator[PNFSprite]:
		yield from self._sprites

	# === PNFSprite property overrides === #

	@property
	def signed_width(self) -> "Numeric":
		if not self._sprites:
			return 0
		return (
			max(sprite.x + sprite.signed_width for sprite in self._sprites) -
			min(sprite.x for sprite in self._sprites)
		)

	@property
	def signed_height(self) -> "Numeric":
		if not self._sprites:
			return 0
		return (
			max(sprite.y + sprite.signed_height for sprite in self._sprites) -
			min(sprite.y for sprite in self._sprites)
		)

	# === PNFSprite property setter overrides === #
	# (Well, some of them.)

	@staticmethod
	def _transform_x(sprite: PNFSprite, x: "Numeric") -> None:
		sprite.x += x

	def _set_x(self, x: "Numeric") -> None:
		self.transform_children(self._transform_x, x - self._x)
		self._x = x

	x = property(PNFSprite.x.fget, _set_x)


	@staticmethod
	def _transform_y(sprite: PNFSprite, y: "Numeric") -> None:
		sprite.y += y

	def _set_y(self, y: "Numeric") -> None:
		self.transform_children(self._transform_y, y - self._y)
		self._y = y

	y = property(PNFSprite.y.fget, _set_y)


	@staticmethod
	def _transform_position(sprite: PNFSprite, position: t.Tuple[int, int]) -> None:
		sprite.position = position

	def _set_position(self, new_position: t.Tuple[int, int]) -> None:
		delta = (new_position[0] - self._x, new_position[1] - self._y)
		self.transform_children(self._transform_position, delta)
		self._x, self._y = new_position

	position = property(PNFSprite.position.fget, _set_position)


	@staticmethod
	def _transform_opacity(sprite: PNFSprite, opacity: int) -> None:
		sprite.opacity += opacity

	def _set_opacity(self, opacity: int) -> None:
		opacity = clamp(opacity, 0, 255)
		self.transform_children(self._transform_opacity, opacity - self._opacity)
		self._opacity = opacity

	opacity = property(PNFSprite.opacity.fset, _set_opacity)
