
import typing as t
from enum import IntEnum

from loguru import logger

if t.TYPE_CHECKING:
	from pyday_night_funkin.pnf_sprite import PNFSprite


class RATING(IntEnum):
	SICK = 0
	GOOD = 1
	BAD = 2
	SHIT = 3


class SUSTAIN_STAGE(IntEnum):
	NONE = 0
	TRAIL = 1
	END = 2


class NOTE_TYPE(IntEnum):
	LEFT = 0
	DOWN = 1
	UP = 2
	RIGHT = 3

	def get_atlas_names(self) -> t.Tuple[str, str, str]:
		"""
		Returns the texture atlas frame sequence names for the given
		arrow type.
		"""
		cap = self.name
		lwr = self.name.lower()
		return (f"arrow{cap}", f"{lwr} press", f"{lwr} confirm")

	def get_order(self) -> int:
		"""
		Returns the screen order the notes should be displayed in.
		By default, same as their enum value.
		"""
		return _NOTE_TYPE_ORDER.get(self, -1)

_NOTE_TYPE_ORDER = {NOTE_TYPE.LEFT: 0, NOTE_TYPE.DOWN: 1, NOTE_TYPE.UP: 2, NOTE_TYPE.RIGHT: 3}


class Note():
	__slots__ = (
		"singer", "time", "type", "sustain", "sustain_stage", "sprite", "rating", "playable"
	)

	def __init__(
		self,
		singer: int,
		time: float,
		type_: NOTE_TYPE,
		sustain: float,
		sustain_stage: SUSTAIN_STAGE,
	) -> None:
		self.singer = singer
		self.time = time
		self.type = type_
		self.sustain = sustain
		self.sustain_stage = sustain_stage
		self.sprite: t.Optional["PNFSprite"] = None
		self.rating = None
		self.playable = False

	def check_playability(self, current_time: float, safe_zone: float) -> None:
		"""
		For notes that need to be played by the player, tests whether
		the note is in the safe zone and sets its playability to `True`
		if it can be played.
		For notes not played by the player, `playable` will always be
		left at `False` and the `rating` will be set to `SICK` once
		the note passed its playtime.
		"""
		if self.rating is not None:
			return

		if self.singer != 1:
			if self.time <= current_time:
				self.rating = RATING.SICK
		else:
			if self.time < current_time - safe_zone:
				self.playable = False
			else:
				self.playable = self.is_playable(current_time, safe_zone)

	def on_hit(self, current_time: float, safe_zone: float) -> None:
		"""
		Should be called when the note was hit. Will set its playability
		to `False` and its rating  depending on the hit timing (# TODO)
		"""
		self.playable = False
		self.rating = RATING.SICK

	def is_playable(self, current_time: float, safe_zone: float) -> bool:
		"""
		Determines whether the note is playable solely based on the
		current song position and the safe zone offset.
		This function may still return `True` if the note is not being
		sung by the player or if it already has been played.
		"""
		return current_time - safe_zone < self.time <= current_time + (safe_zone * 0.5)

	def __gt__(self, other) -> bool:
		if isinstance(other, Note):
			return self.time > other.time
		elif isinstance(other, int):
			return self.time > other
		return NotImplemented

	def __lt__(self, other) -> bool:
		if isinstance(other, Note):
			return self.time < other.time
		elif isinstance(other, int):
			return self.time < other
		return NotImplemented

	def __gte__(self, other) -> bool:
		if isinstance(other, Note):
			return self.time >= other.time
		elif isinstance(other, int):
			return self.time >= other
		return NotImplemented

	def __lte__(self, other) -> bool:
		if isinstance(other, Note):
			return self.time <= other.time
		elif isinstance(other, int):
			return self.time <= other
		return NotImplemented

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} at {id(self):>08X} (type={self.type.name} "
			f"time={self.time})>"
		)
