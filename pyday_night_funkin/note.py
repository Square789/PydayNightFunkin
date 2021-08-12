
import typing as t
from enum import IntEnum

from loguru import logger

if t.TYPE_CHECKING:
	from pyday_night_funkin.pnf_sprite import PNFSprite


class HIT_STATE(IntEnum):
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
		"singer", "time", "type", "sustain", "sustain_stage", "sprite", "hit_state", "playable",
		"missed"
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
		self.hit_state = None
		self.playable = False
		self.missed = False

	def check_playability(self, current_time: float, safe_zone: float) -> None:
		"""
		For notes that need to be played by the player, tests whether
		the note is in the safe zone and sets its playability to True
		if it can be played. If the note left the safe zone, sets the
		note as missed.
		For notes played by the opponent, `playable` will always be
		left at `False` and the `hit_state` will be set to `SICK` once
		the note passed its playtime. They can also not be missed.
		"""
		if self.hit_state is not None:
			return

		if self.singer != 1:
			if self.time <= current_time:
				self.hit_state = HIT_STATE.SICK
		else:
			if self.time < current_time - safe_zone and self.hit_state is None:
				self.playable = False
				self.missed = True
			else:
				self.playable = self.is_playable(current_time, safe_zone)

	def on_hit(self, current_time: float, safe_zone: float) -> None:
		self.hit_state = HIT_STATE.SICK

	def is_playable(self, current_time: float, safe_zone: float) -> bool:
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
