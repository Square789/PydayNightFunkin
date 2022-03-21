
import typing as t

from pyday_night_funkin.core.graphics import PNFGroup
from pyday_night_funkin.core.scene_context import SceneContext


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
		"""


class WorldObject(SceneObject):
	"""
	A scene object occupying space, intended to be drawn.
	"""

	# TODO extract common stuff from subclasses
	# and expand this class with it.
	def __init__(self, x: int = 0, y: int = 0) -> None:
		self._x = x
		self._y = y
		self._rotation = 0


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
		self._context = SceneContext(
			parent_context.batch, PNFGroup(parent_context.group), parent_context.cameras
		)
		for m in self._members:
			m.set_context(self._context)

	def delete(self) -> None:
		for m in self._members:
			m.delete()

	def update(self, dt: float) -> None:
		for m in self._members:
			m.update(dt)
