
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.scene_context import SceneContext

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.types import Numeric


class SceneObject:
	"""
	Standard object that can be registered to a scene hierarchy.
	Similar to FlxBasic.
	"""

	_context = None

	def __init__(self) -> None:
		raise NotImplementedError("You shouldn't init a SceneObject directly!")

	def set_context(self, parent_context: SceneContext) -> None:
		"""
		Called when object is added to a scene/the parent context
		changes.
		Should set up group hierarchy/context based on the given parent
		context's batch and group.
		"""

	def invalidate_context(self) -> None:
		"""
		Called when object is removed from a scene.
		Should clear all possible references to the context.
		By default, will set the context to an empty context.
		"""
		self.set_context(SceneContext())

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


class WorldObject(SceneObject):
	"""
	A scene object occupying two-dimensional geometry, intended to be
	drawn.
	"""

	def __init__(self, x: "Numeric" = 0, y: "Numeric" = 0) -> None:
		self._x = x
		self._y = y
		self._width: "Numeric" = 0
		self._height: "Numeric" = 0
		self._rotation = 0.0
		self._scale = 1.0
		self._scale_x = 1.0
		self._scale_y = 1.0
		self._scroll_factor = (1.0, 1.0)

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

	def screen_center(self, screen_dims: Vec2, x: bool = True, y: bool = True) -> None:
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

	def get_screen_position(self, cam: "Camera") -> Vec2:
		"""
		Returns the screen position the WorldObject's origin is
		displayed at. Note that this may still be inaccurate for
		shaders and rotation.
		"""
		return Vec2(self.x - (cam.x * cam.zoom), self.y - (cam.y * cam.zoom))


class Container(SceneObject):
	"""
	A glorified list wrapper that contains multiple SceneObjects
	and can apply operations to them.
	A container should never have any sort of graphical
	representation, it only serves as a building block of the scene
	hierarchy.
	"""

	def __init__(self) -> None:
		self._members: t.List[SceneObject] = list()

	def add(self, object: SceneObject):
		"""
		Add something to this container.
		"""
		self._members.append(object)
		if self._context is not None:
			object.set_context(self._context)

	def remove(self, object: SceneObject):
		"""
		Remove something from this container.
		"""
		self._members.remove(object)
		object.invalidate_context()

	def set_context(self, parent_context: SceneContext) -> None:
		self._context = parent_context.inherit()
		for m in self._members:
			m.set_context(self._context)

	def delete(self) -> None:
		for m in self._members:
			m.delete()

	def update(self, dt: float) -> None:
		for m in self._members:
			m.update(dt)
