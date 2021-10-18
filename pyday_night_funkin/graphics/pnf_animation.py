
import typing as t
from pyglet.image import Animation
from pyglet.math import Vec2


if t.TYPE_CHECKING:
	from pyglet.image import Texture
	from pyday_night_funkin.graphics.pnf_sprite import PNFSprite
	from pyday_night_funkin.image_loader import FrameInfoTexture


class OffsetAnimationFrame():
	"""
	Similar to pyglet's AnimationFrame, except it also receives
	per-frame offset information a total offset is calculated from
	that should be applied to its receiving sprite's x and y
	coordinates.
	"""

	__slots__ = ("image", "duration", "frame_info")

	def __init__(
		self,
		image: "Texture",
		duration: float,
		frame_info: t.Tuple[int, int, int, int],
	) -> None:
		self.image = image
		self.duration = duration
		self.frame_info = frame_info

	def __repr__(self):
		return (
			f"OffsetAnimationFrame({self.image}, duration={self.duration}, "
			f"frame_info={self.frame_info})"
		)


class PNFAnimation(Animation):
	"""
	Pyglet animation subclass to expand its functionality.
	"""

	def __init__(
		self,
		frames: t.Sequence[OffsetAnimationFrame],
		loop: bool = False,
		offset: t.Optional[t.Union[t.Tuple[int, int], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	):
		"""
		Creates a PNFAnimation.
		"""
		super().__init__(frames)

		if offset is not None and not isinstance(offset, Vec2):
			offset = Vec2(*offset)

		self.offset = offset
		self.loop = loop
		self.tags = set(tags)


class AnimationController():
	"""
	Animation controller class that works with sprites and delivers a
	series of texture and position changes that make up an animation.
	"""
	def __init__(self) -> None:
		self._animations: t.Dict[str, PNFAnimation] = {}
		self.playing: bool = False
		self.current: t.Optional[PNFAnimation] = None
		self.current_name = None
		self._base_box = None
		self._frame_idx = 0
		self._next_dt = 0.0

		self._frame_offset = Vec2()
		"""
		Offset of current animation frame, calculated with animation frame
		dimensions, frame info and 
		Not final, still needs the sprite's scale.
		"""

		self._new_offset = None
		self._new_texture = None

	def _get_post_animate_offset(self) -> Vec2:
		"""
		Should be called after the current frame has changed.
		Calculates the difference between the current frame's and
		the next frame's offset and returns it, while
		"""
		fix, fiy, fiw, fih = self.current_frame.frame_info
		new_frame_offset = Vec2(
			round(fix - (self._base_box[0] - fiw) // 2),
			round(fiy - (self._base_box[1] - fih) // 2),
		)
		old_frame_offset = self._frame_offset
		self._frame_offset = new_frame_offset
		return old_frame_offset - new_frame_offset

	def _set_base_box(
		self, what: t.Union[PNFAnimation, OffsetAnimationFrame, Vec2],
	) -> None:
		if not isinstance(what, Vec2):
			if not isinstance(what, OffsetAnimationFrame):
				if not isinstance(what, PNFAnimation):
					raise TypeError("Invalid type.")
				frame = what.frames[0]
			else:
				frame = what
			new_bb = Vec2(
				frame.frame_info[2] - frame.frame_info[0],
				frame.frame_info[3] - frame.frame_info[1],
			)
		else:
			new_bb = what
		self._base_box = new_bb

	def _set_frame(self, frame: "Texture") -> None:
		self._new_texture = frame

	def _set_offset(self, offset: Vec2) -> None:
		if self._new_offset is None:
			self._new_offset = offset
		else:
			self._new_offset += offset

	def query_new_texture(self) -> t.Optional["Texture"]:
		r = self._new_texture
		self._new_texture = None
		return r

	def query_new_offset(self) -> t.Optional[Vec2]:
		r = self._new_offset
		self._new_offset = None
		return r

	def _detach_animation(self) -> Vec2:
		offset_delta = self._frame_offset
		if self.current.offset is not None:
			offset_delta += self.current.offset

		self._frame_offset = Vec2()

		self.playing = False
		self.current = self.current_name = None

		return offset_delta

	def _on_new_frame(self) -> None:
		self._set_frame(self.current_frame.image.get_texture())
		self._set_offset(self._get_post_animate_offset())

	@property
	def current_frame(self) -> t.Optional[OffsetAnimationFrame]:
		"""
		Returns the current animation's frame or `None` if no animation
		is set.
		"""
		if self.current is None:
			return None
		return self.current.frames[self._frame_idx]

	@property
	def is_set(self) -> bool:
		"""
		Shorthand for `animation_controller.current is not None`.
		Returns whether this controller has an animation set on it.
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

	def has_tag(self, tag: t.Hashable) -> bool:
		"""
		Returns whether the current animation is tagged with the given
		value. False if no animation is set.
		"""
		if self.current is None:
			return False
		return tag in self.current.tags

	def update(self, dt: float) -> None:
		"""
		"""
		if not self.playing:
			return

		_next_dt = self._next_dt
		frame_changed = False
		while dt > _next_dt:
			dt -= _next_dt
			if self._frame_idx >= len(self.current.frames) - 1:
				# Animation has ended
				if self.current.loop:
					self._frame_idx = -1
				else:
					self.playing = False
					return
			self._frame_idx += 1
			frame_changed = True
			_next_dt = self.current.frames[self._frame_idx].duration

		_next_dt -= dt
		if frame_changed:
			self._on_new_frame()

		self._next_dt = _next_dt

	def add_from_frames(
		self,
		name: str,
		anim_data: t.Sequence["FrameInfoTexture"],
		fps: float = 24.0,
		loop: bool = False,
		offset: t.Optional[t.Union[t.Tuple[int, int], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	) -> None:
		"""
		Convenience function to create animation frames directly
		from a sequence of FrameInfoTextures, as retrieved by the
		animation image loader and then add it under the given name.
		"""
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		spf = 1.0 / fps
		frames = [
			OffsetAnimationFrame(tex.texture, spf, tex.frame_info)
			for tex in anim_data
		]

		self.add(name, PNFAnimation(frames, loop, offset, tags))

	def add_by_indices(
		self,
		name: str,
		anim_data: t.Sequence["FrameInfoTexture"],
		indices: t.Sequence[int],
		fps: float = 24.0,
		loop: bool = False,
		offset: t.Optional[t.Union[t.Tuple[int, int], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	):
		"""
		Convenience function to create an animation directly from the
		FrameInfoTextures - retrieved by the animation image loader -
		specified by the given indices and add it under the given name.
		"""
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		spf = 1.0 / fps
		frames = [
			OffsetAnimationFrame(anim_data[i].texture, spf, anim_data[i].frame_info)
			for i in indices
		]

		self.add(name, PNFAnimation(frames, loop, offset, tags))

	def add(self, name: str, animation: PNFAnimation) -> None:
		"""
		Adds an animation to this AnimationController.
		If no base box exists yet it will be set on the base of this
		animation, so try to choose a neutral animation as the first
		one.
		"""
		self._animations[name] = animation
		if self._base_box is None:
			self._set_base_box(animation)

	def play(self, name: str, force: bool = False) -> None:
		if (
			self.current is not None and
			self.current_name == name and self.playing and not force
		):
			return

		# Remove old animation and its offsets
		offset_delta = Vec2()
		if self.current is not None:
			offset_delta += self._detach_animation()

		# Set some variables for new animation
		self.current = self._animations[name]
		self.current_name = name
		self._frame_idx = 0
		self.playing = True

		# Add new animation's offset
		if self.current.offset is not None:
			offset_delta -= self.current.offset
			self._set_base_box(self.current)

		# Set first frame
		frame = self.current.frames[0]
		self._next_dt = frame.duration
		self._set_offset(offset_delta)
		self._on_new_frame()

	def pause(self) -> None:
		self.playing = False

	def stop(self) -> None:
		if self.current is not None:
			self._set_offset(self._detach_animation())
