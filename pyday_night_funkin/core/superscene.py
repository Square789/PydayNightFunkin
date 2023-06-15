

from pyday_night_funkin.core.camera import SimpleCamera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.scene import SceneContext


class SuperScene:
	"""
	A SuperScene is a stripped-down version of a scene
	lacking most of its convenience features.
	It is similar to openfl's `Sprite`s (or `DisplayObjectContainer`s?)
	in that they are supposed to be added ontop of the game's scene
	hierarchy itself.
	"""

	def __init__(self, width: int, height: int) -> None:
		self.batch = PNFBatch()
		self._camera = SimpleCamera(width, height)
		self._cameras = (self._camera,)

	def get_context(self, group: PNFGroup) -> SceneContext:
		"""
		Convenience method to get a `SceneContext` of the superscene's
		batch, the given group and the superscene's camera.
		"""
		return SceneContext(self.batch, group, self._cameras)

	def draw(self) -> None:
		"""
		Draws the superscene.
		"""
		self._camera.maybe_update_ubo()
		self.batch.draw(self._camera)
