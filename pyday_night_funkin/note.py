
import typing as t
from enum import IntEnum

from pyday_night_funkin.pnf_sprite import PNFSprite


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
	__slots__ = ("singer", "time", "type", "sustain", "sprite", "sustain_stage")
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
		self.sprite = None
		self.sustain_stage = sustain_stage

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
