
import typing as t
import weakref


class SceneObject:
	"""
	Standard object that can be registered to a scene hierarchy.
	Similar to FlxBasic or FlxObject i guess.
	"""

	def on_scene_add(self, parent):
		pass


class Container(SceneObject):
	"""
	A group that contains multiple SceneObjects and can apply
	operations to them.
	"""
	def __init__(self) -> None:
		super().__init__()
		self._members: t.List["SceneObject"] = []

	def add(self, object: SceneObject):
		"""
		Add something to this container.
		"""
		self._members.append(object)
		object.on_scene_add(self)

	def remove(self, object: SceneObject):
		"""
		Remove something from this container.
		"""
		self._members.remove(object)
