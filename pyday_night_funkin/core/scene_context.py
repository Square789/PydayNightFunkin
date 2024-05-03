
import typing as t
from pyday_night_funkin.core.camera import SimpleCamera

from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup, get_default_batch

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import SimpleCamera


class SceneContext:
	"""
	A scene contex is fancy talk for a batch and a group in a slotted
	container class.
	Basically a bundling class for the things needed to interact with
	the graphics backend.

	See ``CamSceneContext`` which additionally contains cameras to
	draw to.

	Context is passed down the entire hierarchy of a scene.
	Each drawable/container requires its own group, (which is usually
	just created as a child group to the group of the received context),
	but the others are usually references to the same object.
	"""

	# TODO docstrings all wrong fix once stableee

	__slots__ = ("batch", "group")

	def __init__(
		self,
		batch: "PNFBatch",
		group: t.Optional["PNFGroup"],
	) -> None:
		"""
		Creates a new context.
		"""

		self.batch = batch
		"""The scene's batch."""

		self.group = group
		"""Group that defines a position/order in the scene tree."""

	@classmethod
	def create_empty(cls):
		"""
		Creates an empty SceneContext using the default batch and an
		empty group.
		"""
		return cls(get_default_batch(), PNFGroup())

	def inherit(self, order: int = 0) -> "SceneContext":
		"""
		Returns a new context which shares this context's batch and
		cameras and has a new PNFGroup whose parent is this context's
		group.
		Convenience method, as this has to be done in drawable setup
		relatively often.
		"""
		return SceneContext(self.batch, PNFGroup(self.group, order))


class CamSceneContext(SceneContext):
	"""
	Scene context subclass which includes cameras.

	This subclass is required to be passed to drawables which use the cameras
	to specify which cameras they want to be drawn to. It is not required by
	container-like ``SceneObject``s that lack graphical representation.
	"""

	__slots__ = ("cameras",)

	def __init__(
		self,
		batch: PNFBatch,
		group: t.Optional[PNFGroup],
		cameras: t.Iterable[SimpleCamera],
	) -> None:
		super().__init__(batch, group)

		self.cameras = tuple(cameras)
		"""
		The cameras the owning drawable should be drawn with.
		"""

	@classmethod
	def create_empty(cls):
		return cls(get_default_batch(), PNFGroup(), ())

	def inherit(self, order: int = 0) -> "CamSceneContext":
		return CamSceneContext(self.batch, PNFGroup(self.group, order), self.cameras)
