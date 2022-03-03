
import typing as t

from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFBatch, get_default_batch, PNFGroup


class Context():
	"""
	Graphics context, which is fancy talk for a batch, a group and
	cameras in a slotted container class.
	"""

	__slots__ = ("batch", "cameras", "group")

	def __init__(
		self,
		batch: t.Optional["PNFBatch"] = None,
		group: t.Optional["PNFGroup"] = None,
		cameras: t.Optional[t.Union["Camera", t.Iterable["Camera"]]] = None,
	) -> None:
		"""
		Creates a new context.
		If no `batch` is given, it will be set to be the default batch.
		If no `group` is given, it will be set to an empty group
		without state mutators and no parent.
		If no `cameras` are given, it will be set to the global dummy
		camera.
		"""
		self.batch = batch or get_default_batch()
		self.group = group or PNFGroup()
		if isinstance(cameras, Camera):
			self.cameras = (cameras,)
		else:
			self.cameras = cameras or (Camera.get_dummy(),)
