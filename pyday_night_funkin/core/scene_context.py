
import typing as t

from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup, get_default_batch


class SceneContext():
	"""
	A scene context, which is fancy talk for a batch, a group and
	cameras in a slotted container class. Basically a bundling class
	for the things needed to interact with the graphics backend.

	This thing is in a way passed down the entire hierarchy of a
	scene. Each drawable/container requires its own group, (which)
	is usually just created as a child group to the group of the
	received context, but the other two are references to the same
	object.
	"""

	__slots__ = ("batch", "cameras", "group")

	def __init__(
		self,
		batch: t.Optional["PNFBatch"] = None,
		group: t.Optional["PNFGroup"] = None,
		cameras: t.Optional[t.Iterable["Camera"]] = None,
	) -> None:
		"""
		Creates a new context.
		If no `batch` is given, it will be set to be the default batch.
		If no `group` is given, it will be set to an empty group with
		no parent.
		If no `cameras` are given, will be set to only the global dummy
		camera.
		"""

		self.batch = batch or get_default_batch()
		"""The scene's batch."""

		self.group = group or PNFGroup()
		"""Group that defines a position/order in the scene tree."""

		self.cameras = tuple(cameras or (Camera.get_dummy(),))
		"""
		The cameras the owning drawable should be drawn with.
		I am not happy with how these are in here since they don't
		really have much to do with the scene, but hey, nothing is
		perfect.
		"""

	def inherit(self) -> "SceneContext":
		"""
		Returns a new context which shares this context's batch and
		cameras and has a new PNFGroup whose parent is this context's
		group.
		Convenience method, as this has to be done in drawable setup
		relatively often.
		"""
		return SceneContext(self.batch, PNFGroup(self.group), self.cameras)
