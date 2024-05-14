

from pyday_night_funkin.core.camera import SimpleCamera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.scene_context import CamSceneContext


class SuperScene:
	"""
	A SuperScene is just a container for a batch and cameras and lacks most
	standard scene features.

	It is similar to openfl's `Sprite`s (or `DisplayObjectContainer`s?)
	in that they are supposed to be added ontop of the game's scene
	hierarchy itself.
	"""

	def __init__(self, width: int, height: int) -> None:
		self.batch = PNFBatch()
		self._camera = SimpleCamera(width, height)
		self._cameras = (self._camera,)

	def get_context(self, group: PNFGroup, order: int = 0) -> CamSceneContext:
		"""
		Convenience method to get a `CamSceneContext` of the superscene's
		batch and the superscene's camera with a new group parented to
		the given group with the given order.
		"""
		return CamSceneContext(self.batch, PNFGroup(group, order), self._cameras)

	def draw(self) -> None:
		"""
		Draws the superscene.
		"""
		self._camera.maybe_update_ubo()
		if self._camera.visible:
			self.batch.draw(self._camera)
