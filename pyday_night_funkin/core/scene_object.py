
import typing as t

from pyday_night_funkin.core.graphics import PNFGroup, get_default_batch

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.context import Context


class SceneObject:
	"""
	Standard object that can be registered to a scene hierarchy.
	Similar to FlxBasic.
	"""

	_context = None

	def set_context(self, parent_context: "Context") -> None:
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
		"""

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


class Container(SceneObject):
	"""
	A glorified set wrapper that contains multiple SceneObjects
	and can apply operations to them.
	A container should never have any sort of graphical
	representation, it only serves as a building block of the scene
	hierarchy.
	"""

	def __init__(self) -> None:
		self._members: t.Set[SceneObject] = set()

	def add(self, object: SceneObject):
		"""
		Add something to this container.
		"""
		self._members.add(object)
		if self._context is not None:
			object.set_context(self._context)

	def remove(self, object: SceneObject):
		"""
		Remove something from this container.
		"""
		self._members.remove(object)
		object.invalidate_context()

	def set_context(self, parent_context: "Context") -> None:
		self._context = Context(parent_context.batch, PNFGroup(parent=parent_context.group))
		for spr in self._members:
			spr.set_context(self._context)

	def invalidate_context(self) -> None:
		self.set_context(Context(get_default_batch(), None))

	def delete(self) -> None:
		for spr in self._members:
			spr.delete()

	def update(self, dt: float) -> None:
		for spr in self._members:
			spr.update(dt)
