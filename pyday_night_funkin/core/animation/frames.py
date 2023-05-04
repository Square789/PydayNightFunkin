
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


def _try_int(v: object) -> int:
	try:
		return int(v)
	except ValueError:
		return 0


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

	def collect_by_prefix(self, prefix: str) -> t.List[t.Tuple[AnimationFrame, int]]:
		"""
		Returns all `AnimationFrame`s whose name starts with the given
		prefix, as well as their frame designation in a list of tuples.
		"""
		prefix_candidates = [
			frame for frame in self.frames
			if frame.name is not None and frame.name.startswith(prefix)
		]
		if not prefix_candidates:
			raise ValueError(f"No frames with prefix {prefix!r} found.")

		prefix_len = len(prefix)
		suffix_start_idx = prefix_candidates[0].name.find('.', prefix_len)
		# If a dot is present, try converting to an integer behind the prefix and
		# in front of the dot.
		# Otherwise, try converting whatever is behind the prefix to an integer.
		# Point of this is to deal with frames like `x-000.png`, `x-001.png`;
		# assumes the length of `.png` will never change and just cuts these off.
		# All of this is not really relevant in FNF, no animation name contains
		# dots i believe
		slc = slice(prefix_len, None if suffix_start_idx == -1 else suffix_start_idx)
		return [(f, _try_int(f.name[slc])) for f in prefix_candidates]

	def collect_ordered_by_prefix(self, prefix: str) -> t.List[AnimationFrame]:
		"""
		Returns all frames for the given prefix, sorted by the indices
		in their names.
		"""
		return [f for (f, _) in sorted(self.collect_by_prefix(prefix), key=lambda x: x[1])]

	def __getitem__(self, i: int) -> AnimationFrame:
		return self.frames[i]
