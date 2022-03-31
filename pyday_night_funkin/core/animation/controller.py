
import typing as t

from loguru import logger
from pyglet.math import Vec2

from .animation import Animation
from .frames import AnimationFrame

if t.TYPE_CHECKING:
	from pyglet.image import Texture
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.core.types import Numeric


def _try_int(v: object) -> int:
	try:
		return int(v)
	except ValueError:
		return 0


def _collect_prefixed_animation_frames(
	frames: t.Iterable[AnimationFrame], prefix: str
) -> t.List[t.Tuple[AnimationFrame, int]]:
	prefix_candidates = [
		frame for frame in frames
		if frame.name is not None and frame.name.startswith(prefix)
	]
	if not prefix_candidates:
		raise ValueError(f"No frames with prefix {prefix!r} found.")

	prefix_len = len(prefix)
	suffix_start_idx = prefix_candidates[0].name.find('.', prefix_len)
	slc = slice(prefix_len, None if suffix_start_idx == -1 else suffix_start_idx)
	return [(f, _try_int(f.name[slc])) for f in prefix_candidates]


class AnimationController:

	def __init__(self, owner: "PNFSprite") -> None:
		"""
		Initializes an AnimationController.

		:param owner: The sprite this controller belongs to.
		"""
		self._animations: t.Dict[str, Animation] = {}
		self.current: t.Optional[Animation] = None
		self.current_name: t.Optional[str] = None

		self._owner_sprite = owner

	def _detach_animation(self) -> None:
		self.current.stop()
		self.current = self.current_name = None

	def _on_new_frame(self) -> None:
		self._owner_sprite._set_frame(self.current.cur_index)

	def get_current_frame_index(self) -> t.Optional[int]:
		"""
		Returns the current animation's frame index or `None` if no
		animation is set.
		"""
		if self.current is None:
			return None
		return self.current.cur_index

	@property
	def is_set(self) -> bool:
		"""
		Returns whether this controller has an animation set on it.
		Shorthand for `animation_controller.current is not None`.
		"""
		return self.current is not None

	@property
	def loop(self) -> bool:
		"""
		Returns whether the current animation loops.
		False if no animation is set.
		"""
		if self.current is None:
			return False
		return self.current.loop

	def exists(self, animation_name: str) -> bool:
		"""
		Returns whether an animation with the given name exists.
		"""
		return animation_name in self._animations

	def has_tag(self, tag: t.Hashable) -> bool:
		"""
		Returns whether the current animation is tagged with the given
		value. False if no animation is set.
		"""
		if self.current is None:
			return False
		return tag in self.current.tags

	def update(self, dt: float) -> None:
		if self.current is not None:
			if self.current.update(dt):
				self._on_new_frame()

	@staticmethod
	def get_frames_by_prefix(
		frames: t.Iterable[AnimationFrame], prefix: str
	) -> t.List[AnimationFrame]:
		"""
		Returns all frames for the given prefix, sorted by the indices
		in their names.
		"""
		return [f for f, _ in _collect_prefixed_animation_frames(frames, prefix)]

	def add_by_prefix(
		self,
		name: str,
		prefix: str,
		fps: float = 24.0,
		loop: bool = True,
		offset: t.Optional[t.Union[t.Tuple[int, int], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	) -> None:
		"""
		TODO docstring
		"""
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		frames = self._owner_sprite.frames
		prefix_candidates = _collect_prefixed_animation_frames(frames, prefix)
		prefix_candidates.sort(key=lambda f: f[1])

		self.add(
			name,
			Animation([frames.index_of(f) for f, _ in prefix_candidates], fps, loop, offset, tags),
		)

	def add_by_indices(
		self,
		name: str,
		prefix: str,
		indices: t.Sequence[int],
		fps: float = 24.0,
		loop: bool = True,
		offset: t.Optional[t.Union[t.Tuple[int, int], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	) -> None:
		"""
		# TODO doc
		"""
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		frames = self._owner_sprite.frames
		index_map = {}
		for frame, idx in _collect_prefixed_animation_frames(frames, prefix):
			if idx not in index_map:
				index_map[idx] = frame
			else:
				# logger.info(f"Found >1 frame with index {idx} for prefix {prefix}, ignoring.")
				pass # `GF Dancing Beat` keeps spamming the log here, silencing it ¯\_(ツ)_/¯

		self.add(
			name,
			Animation([frames.index_of(index_map[i]) for i in indices], fps, loop, offset, tags),
		)

	def add(self, name: str, animation: Animation) -> None:
		"""
		Adds an animation to this AnimationController.
		"""
		self._animations[name] = animation

	def delete_animations(self) -> None:
		"""
		Deletes all animations from the AnimationController.
		Also stops a potentially running one.
		"""
		if self.current is not None:
			self._detach_animation()
		self._animations = {}

	def remove(self, name: str) -> None:
		"""
		Removes an animation from this AnimationController.
		Stops it if it is the one playing.
		"""
		if self.current_name == name:
			self._detach_animation()
		self._animations.pop(name)

	def play(self, name: str, force: bool = False, frame: int = 0) -> None:
		# Remove old animation
		if self.current is not None and self.current_name != name:
			self._detach_animation()

		# Set some variables for new animation
		self.current = self._animations[name]
		self.current_name = name
		self.current.play(force, frame)

		# Apply new animation's offset and first frame
		if self.current.offset is not None:
			self._owner_sprite.offset = tuple(-self.current.offset)
		self._on_new_frame()

	def stop(self) -> None:
		if self.current is not None:
			self._detach_animation()
