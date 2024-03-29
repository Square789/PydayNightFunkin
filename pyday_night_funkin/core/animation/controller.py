
import typing as t

from pyglet.math import Vec2

from .animation import Animation

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


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
		self._owner_sprite.set_frame_by_index(self.current.cur_index)

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

	def add_by_prefix(
		self,
		name: str,
		prefix: str,
		fps: float = 24.0,
		loop: bool = True,
		offset: t.Optional[t.Union[t.Tuple[float, float], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	) -> None:
		"""
		Adds an animation built from the sprite's frames sharing the
		prefix `prefix`. The animation frames will be sorted given by
		numbers in the frame names, so that frames `run0`, `run1` and
		`run3` will play in that order for a prefix of `run`. If a dot
		is present in the names (`x0000.png`, `x0001.png`), it serves
		as a cutoff point for the numbers, **but assumes the dot to be
		in the same position as the first encountered frame for each
		frame.**
		The rest of the options is passed into the animation.
		"""
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		frames = self._owner_sprite.frames
		prefix_candidates = frames.collect_ordered_by_prefix(prefix)

		self.add(
			name,
			Animation([frames.index_of(f) for f in prefix_candidates], fps, loop, offset, tags),
		)

	def add_by_indices(
		self,
		name: str,
		prefix: str,
		indices: t.Iterable[int],
		fps: float = 24.0,
		loop: bool = True,
		offset: t.Optional[t.Union[t.Tuple[float, float], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	) -> None:
		"""
		Finds all the sprite's frames whose names share the prefix
		`prefix` and then adds an animation composed from the frame
		indices as they're found in the frame names. See
		`add_by_prefix` for prefix oddities.
		The rest of the options is passed into the animation.
		"""
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		frames = self._owner_sprite.frames
		index_map = {}
		for frame, idx in frames.collect_by_prefix(prefix):
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

	def remove_safe(self, name: str) -> None:
		"""
		Calls into `remove` only if an animation of this name
		actually exists.
		"""
		if self.exists(name):
			self.remove(name)

	def remove(self, name: str) -> None:
		"""
		Removes an animation from this AnimationController.
		Stops it if it is the one playing.
		"""
		if self.current_name == name:
			self._detach_animation()
		self._animations.pop(name)

	def play(self, name: str, force: bool = False, frame: int = 0) -> None:
		"""
		Plays the animation given by `name` starting from frame
		`frame`.
		This will not have an effect if the animation is already
		playing, unless the `force` parameter is set to `True`.
		"""
		# Remove old animation
		if self.current is not None and self.current_name != name:
			self._detach_animation()

		# Set some variables for new animation
		self.current = self._animations[name]
		self.current_name = name
		self.current.play(force, frame)

		# Apply new animation's offset and first frame
		if self.current.offset is not None:
			self._owner_sprite.offset = tuple(self.current.offset)
		self._on_new_frame()

	def stop(self) -> None:
		"""
		Immediatedly stops the current animation; none will be playing
		afterwards.
		"""
		if self.current is not None:
			self._detach_animation()

	def finish(self) -> None:
		"""
		Immediatedly finishes the current animation, advancing it to
		its last frame, then stops it.
		Whether it's looped or not does not have any effect.
		"""
		if self.current is not None:
			if self.current.finish():
				self._on_new_frame()
			self._detach_animation()
