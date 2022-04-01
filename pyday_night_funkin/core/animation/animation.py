
import typing as t

from pyglet.math import Vec2

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.types import Numeric



class Animation:
	"""
	Animation class that steals all its concepts from the FlxAnimation.
	Each Animation contains a bunch of indices, information about
	whether it should be looped and also runtime information i.e.
	defining its playtime/whether it's playing.
	"""

	def __init__(
		self,
		frame_indices: t.Sequence[int],
		fps: float = 24.0,
		loop: bool = False,
		offset: t.Optional[t.Union[t.Tuple[int, int], Vec2]] = None,
		tags: t.Sequence[t.Hashable] = (),
	):
		if not frame_indices:
			raise ValueError("Animations must have at least one frame!")

		self._frame_indices = frame_indices
		self.length = len(frame_indices)

		if offset is not None and not isinstance(offset, Vec2):
			offset = Vec2(*offset)
		self.offset = offset

		self.fps = fps
		self.spf = 1 / fps
		self.loop = loop
		self.tags = set(tags)

		self.playing = False
		self.playtime = 0.0
		self._cur_index_index = 0 # yeah, good name, i'm aware.
		self.cur_index = frame_indices[0]
		"""
		The currently shown index of the animation's frame indices.
		"""

	def stop(self) -> None:
		self.playing = False

	def play(self, force: bool, frame: int) -> None:
		if not force and self.playing:
			return

		self.playing = True
		self.playtime = 0.0

		if frame < 0 or frame >= self.length:
			raise ValueError("Frame index out of bounds.")
		self._cur_index_index = frame
		self.cur_index = self._frame_indices[frame]

	def update(self, dt: float) -> bool:
		if not self.playing:
			return

		self.playtime += dt
		frame_changed = False
		while self.playtime > self.spf and self.playing:
			self.playtime -= self.spf
			if self._cur_index_index >= self.length - 1:
				if self.loop:
					self._cur_index_index = 0
					self.cur_index = self._frame_indices[0]
					frame_changed = self.length > 1
				else:
					self.playing = False
			else:
				self._cur_index_index += 1
				self.cur_index = self._frame_indices[self._cur_index_index]
				frame_changed = True

		return frame_changed
