
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.utils import dump_id

if t.TYPE_CHECKING:
	from pyglet.image import Texture


class AnimationFrame:
	"""
	Composite class to store per-frame offsets found inside
	a data file alongside a `Texture` or `TextureRegion`.
	"""

	__slots__ = ("texture", "offset", "source_dimensions", "name")

	def __init__(
		self,
		texture: "Texture",
		offset: Vec2 = Vec2(0, 0),
		source_dimensions: Vec2 = Vec2(0, 0),
		name: t.Optional[str] = None
	) -> None:
		self.texture = texture
		self.offset = offset
		self.source_dimensions = source_dimensions
		self.name = name

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} at {dump_id(self)}, texture={self.texture!r}, "
			f"offset={self.offset!r}, source_dimensions={self.source_dimensions!r}, "
			f"name={self.name!r}>"
		)


class FrameCollection:
	"""
	A frame collection is really just a list and a dict for storing
	`AnimationFrame`s in a way that makes sense for the animation
	system.
	"""

	def __init__(self) -> None:
		self.frames: t.List[AnimationFrame] = []
		self._index_map: t.Dict[AnimationFrame, int] = {}

	def add_frame(
		self,
		texture: "Texture",
		source_size: Vec2,
		offset: Vec2,
		name: t.Optional[str] = None,
	) -> None:
		"""
		Creates a new `AnimationFrame` from the given parameters adds
		it to this `FrameCollection`.
		"""
		frame = AnimationFrame(texture, offset, source_size, name)
		self._index_map[frame] = len(self.frames)
		self.frames.append(frame)

	def index_of(self, frame: AnimationFrame) -> int:
		"""
		Returns the index of an `AnimationFrame` in this
		`FrameCollection`, or raises a `KeyError` if it's unknown.
		"""
		if frame not in self._index_map:
			raise KeyError("Frame unknown to FrameCollection.")
		return self._index_map[frame]

	def __getitem__(self, i: int) -> AnimationFrame:
		return self.frames[i]
