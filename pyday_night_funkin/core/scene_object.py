
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFGroup
from pyday_night_funkin.core.scene_context import CamSceneContext, SceneContext

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import SimpleCamera
	from pyday_night_funkin.core.types import CoordIndexable, Numeric


SceneContextT = t.TypeVar("SceneContextT", bound=SceneContext)


# So, SceneObjects have a SceneContext. There's two scene context types.
# The base one and the CamSceneContext which comes with cameras.
# Each SceneObject subtype has one of these contexts, however have both setters.
#
# SceneObject
# Container
# Scene       set_cam_context -> set_context.
# These types do not have a graphical representation, no cameras, and reject cameras softly
# by just pretending the CamSceneContext is a standard SceneContext
#
# WorldObject
# PNFSprite
# PNFText
# PNFSpriteContainer...
# These types do have graphical representation (or at least in the sprite container's case
# propagate it,) so their set_context actually calls into set_cam_context with their current
# context's cameras applied.

# NOTE: Only way i could figure out how to have ``SceneObject._context`` resolve to a SceneContext
# and ``WorldObject._context`` to a CamSceneContext.
# In order to not run Generic.__new__ all the time, perform TYPE_CHECKING awfulness.
# Since this only has to be repeated for ``WorldObject`` and ``Container``, it's an okay
# micro-optimization probably.

class SceneObject(t.Generic[SceneContextT] if t.TYPE_CHECKING else object):
	"""
	Standard object that can be registered to a scene hierarchy.
	Similar to FlxBasic.
	"""

	def __init__(self, context: SceneContextT) -> None:
		self._context: SceneContextT = context

	def set_context(self, new_context: SceneContext) -> None:
		"""
		Sets this ``SceneObject``'s ``SceneContext``.
		Typically called when it is added to a scene/its parent's
		context undergoes a radical change.

		If this SceneObject is a drawable, this method must add it to
		the given context's batch.
		"""
		raise NotImplementedError()

	def set_cam_context(self, new_cam_context: CamSceneContext) -> None:
		raise NotImplementedError()

	def set_context_group(self, new_parent: t.Optional[PNFGroup]) -> None:
		"""
		Modifies only a ``SceneObject``'s context's group.

		Default implementation generates an entirely new ``SceneContext``
		and passes that to ``set_context``.
		"""
		self.set_context(SceneContext(self._context.batch, new_parent))

	def invalidate_context(self) -> None:
		"""
		Called when this ``SceneObject`` is removed from a scene.
		Should clear all possible references to the context.
		By default, will set the context to an empty context.
		"""
		self.set_context(SceneContext.create_empty())

	def delete(self) -> None:
		"""
		Should do anything necessary to free up this scene object's
		resources, remove it from the scene hierarchy and prevent its
		display.
		"""

	def update(self, dt: float) -> None:
		"""
		The one and only update function.
		Put your game logic here.

		:param dt: The time difference from the last update call, in
			seconds.
		"""


class WorldObject(SceneObject[CamSceneContext] if t.TYPE_CHECKING else SceneObject):
	"""
	A scene object occupying two-dimensional geometry, intended to be
	drawn.
	"""

	def __init__(
		self,
		x: "Numeric" = 0,
		y: "Numeric" = 0,
		context: t.Optional[CamSceneContext] = None,
	) -> None:
		super().__init__(CamSceneContext.create_empty() if context is None else context)

		self._x = x
		self._y = y
		self._width: "Numeric" = 0
		self._height: "Numeric" = 0
		self._rotation = 0.0
		self._scale = 1.0
		self._scale_x = 1.0
		self._scale_y = 1.0
		self._scroll_factor = (1.0, 1.0)

	def set_context(self, new_context: SceneContext) -> None:
		self.set_cam_context(
			CamSceneContext(new_context.batch, new_context.group, self._context.cameras)
		)

	def set_cam_context(self, new_context: CamSceneContext) -> None:
		"""
		Sets this ``WorldObject``'s ``CamSceneContext``.

		Prefer this method for ``WorldObject``s.
		On those, ``set_context`` creates a new ``CamSceneContext`` with
		the current cameras and then calls into this method, which is a bit
		wasteful!
		"""
		raise NotImplementedError()

	def set_context_cameras(self, new_cameras: t.Sequence[Camera]) -> None:
		"""
		Modifies only a ``WorldObject``'s context's cameras.

		Default implementation generates an entirely new ``CamSceneContext``
		and passes that to ``set_cam_context``.
		"""
		self.set_cam_context(
			CamSceneContext(self._context.batch, self._context.group, new_cameras),
		)

	# NOTE: I would add a bunch of x, y, position, rotation etc. properties
	# here. Unfortunately, when it comes to inheriting properties is where
	# python really stops shining, you'd end up either having properties
	# delegate to a method which is then overridden, or have to redefine
	# the property in the subclass anyways. I tested it, code in
	# `dev_notes\property_subclass.py`, the former is nearly twice as slow.
	# Premature optimization this, premature optimization that, but these
	# properties are being used dozens of times each frame, so I will:
	# - Repeat them in each subclass
	# - Not put them here since WorldObjects aren't ever being created
	#   themselves so it'd be just dead code for show

	@property
	def width(self) -> "Numeric":
		return self._width

	@property
	def height(self) -> "Numeric":
		return self._height

	def screen_center(self, screen_dims: "CoordIndexable", x: bool = True, y: bool = True) -> None:
		"""
		Sets the WorldObject's world position so that it is centered
		on screen. (Ignoring camera and scroll factors)
		`x` and `y` can be set to false to only center the sprite
		along one of the axes.
		"""
		if x:
			self.x = (screen_dims[0] - self.width) // 2
		if y:
			self.y = (screen_dims[1] - self.height) // 2

	def get_midpoint(self) -> Vec2:
		"""
		Returns the middle point of this WorldObject, based on its
		position and dimensions.
		"""
		return Vec2(self.x + self._width * 0.5, self.y + self._height * 0.5)

	def get_screen_position(self, cam: "SimpleCamera") -> Vec2:
		"""
		Returns the screen position the WorldObject's origin is
		displayed at. Note that this may still be inaccurate for
		shaders and rotation.
		"""
		return Vec2(self.x - (cam.x * cam.zoom), self.y - (cam.y * cam.zoom))
