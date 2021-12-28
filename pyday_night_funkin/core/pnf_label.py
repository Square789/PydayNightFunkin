
import typing as t

from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.pyglet_tl_patch import TLLabel
from pyday_night_funkin.core.scene_object import SceneObject

if t.TYPE_CHECKING:
	pass


class PNFLabel(TLLabel, SceneObject):
	"""
	Scene object wrapping a (hacked) pyglet label.
	"""

	def __init__(
		self,
		context: t.Optional[Context] = None,
		*args,
		**kwargs,
	) -> None:
		super(SceneObject, self).__init__() # Technically useless, but for cleanliness' sake
		self._context = context or Context()

		kwargs.setdefault("batch", self._context.batch)
		kwargs.setdefault("group", self._context.group)

		super().__init__(*args, **kwargs)



	def set_context(self, parent_context: "Context") -> None:
		old_batch = self._context.batch
		old_group = self._context.group
		old_camera = self._context.camera
		new_batch = parent_context.batch
		new_group = parent_context.group
		new_camera = parent_context.camera

	def invalidate_context(self) -> None:
		pass

	def delete(self) -> None:
		pass
