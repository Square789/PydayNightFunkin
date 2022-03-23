
import typing as t
from pyglet.math import Vec2


if t.TYPE_CHECKING:
	from pyglet.image import Texture
	from pyday_night_funkin.core.types import Numeric
	from pyday_night_funkin.core.utils import FrameInfoTexture


class OffsetAnimationFrame:
	"""
	Similar to pyglet's AnimationFrame, except it also receives
	per-frame offset information. A total offset is calculated from
	that and should be applied to its receiving sprite's x and y
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


class PNFAnimation:
	"""
	Animation class that steals all its concepts from the FlxAnimation.
	Each PNFAnimation contains a bunch of OffsetAnimationFrames,
	information about whether it should be looped and also runtime
	information i.e. defining its playtime/whether it's playing.
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
		if not frames:
			raise ValueError("Animation must have at least one frame!")
		self.frames = frames

		if offset is not None and not isinstance(offset, Vec2):
			offset = Vec2(*offset)
		self.offset = offset

		self.loop = loop
		self.tags = set(tags)

		self.playing = False
		self.playtime = 0.0
		self.cur_frame_idx = 0

	def stop(self) -> None:
		self.playing = False

	def play(self, force: bool, frame: int) -> None:
		if not force and self.playing:
			return

		self.playing = True
		self.playtime = 0.0

		if frame < 0 or frame >= len(self.frames):
			raise ValueError("Frame index out of bounds.")
		self.cur_frame_idx = frame

	def update(self, dt: float) -> bool:
		if not self.playing:
			return

		self.playtime += dt
		frame_changed = False
		while self.playtime > self.frames[self.cur_frame_idx].duration and self.playing:
			self.playtime -= self.frames[self.cur_frame_idx].duration
			if self.cur_frame_idx >= len(self.frames) - 1:
				if self.loop:
					self.cur_frame_idx = 0
					frame_changed = len(self.frames) > 1
				else:
					self.playing = False
			else:
				self.cur_frame_idx += 1
				frame_changed = True

		return frame_changed

class AnimationController:
	"""
	Animation controller class that works with sprites and delivers a
	series of texture and position changes that make up an animation.
	You guessed it - copies FlxAnimationController behavior.
	"""
	def __init__(self) -> None:
		self._animations: t.Dict[str, PNFAnimation] = {}
		self.current: t.Optional[PNFAnimation] = None
		self.current_name = None
		self._base_box = None

		self._frame_offset = (0, 0)
		"""
		Offset of current animation frame, calculated with animation
		frame dimensions, frame info and base box.
		Not final, still needs the sprite's scale.
		"""

		self._new_offset = None
		"""
		Per-animation offset.
		"""

		self._new_texture = None

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

	def _set_offset(self, offset: t.Optional[t.Tuple["Numeric", "Numeric"]]) -> None:
		self._new_offset = offset

	def _set_frame_offset(self, frame_offset: t.Optional[t.Tuple["Numeric", "Numeric"]]) -> None:
		self._frame_offset = frame_offset

	def query_new_texture(self) -> t.Optional["Texture"]:
		r = self._new_texture
		self._new_texture = None
		return r

	def query_new_offset(self) -> t.Optional[t.Tuple["Numeric", "Numeric"]]:
		r = self._new_offset
		self._new_offset = None
		return r

	def query_new_frame_offset(self) -> t.Optional[t.Tuple["Numeric", "Numeric"]]:
		r = self._frame_offset
		self._frame_offset = None
		return r

	def _detach_animation(self) -> None:
		self._set_frame_offset((0, 0))
		self._set_offset((0, 0))
		self.current.stop()
		self.current = self.current_name = None

	def _on_new_frame(self) -> None:
		cf = self.get_current_frame()
		self._set_frame(cf.image.get_texture())

		fix, fiy, fiw, fih = cf.frame_info
		self._set_frame_offset((
			-round(fix - (self._base_box[0] - fiw) // 2),
			-round(fiy - (self._base_box[1] - fih) // 2),
		))

	def get_current_frame(self) -> t.Optional[OffsetAnimationFrame]:
		"""
		Returns the current animation's frame or `None` if no animation
		is set.
		"""
		if self.current is None:
			return None
		return self.current.frames[self.current.cur_frame_idx]

	def get_current_frame_index(self) -> t.Optional[int]:
		"""
		Returns the current animation's frame index or `None` if no
		animation is set.
		"""
		if self.current is None:
			return None
		return self.current.cur_frame_idx

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

	def add_from_frames(
		self,
		name: str,
		anim_data: t.Sequence["FrameInfoTexture"],
		fps: float = 30.0,
		loop: bool = True,
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
		indices: t.Iterable[int],
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

	def play(self, name: str, force: bool = False, frame: int = 0) -> None:
		# Remove old animation
		if self.current is not None and self.current_name != name:
			self._detach_animation()

		# Set some variables for new animation
		self.current = self._animations[name]
		self.current_name = name
		self.current.play(force, frame)

		c_off = Vec2(0, 0)
		if self.current.offset is not None:
			c_off -= self.current.offset
			self._set_base_box(self.current)

		# Set first frame
		self._set_offset(tuple(c_off))
		self._on_new_frame()

	def stop(self) -> None:
		if self.current is not None:
			self._detach_animation()
