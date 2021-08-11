
from dataclasses import dataclass
from enum import IntEnum
import typing as t


class KEY(IntEnum):
	LEFT = 0
	DOWN = 1
	UP = 2
	RIGHT = 3


@dataclass
class Config():
	"""
	Stores game configuration. Some of these options make gameplay
	easier or harder.

	`scroll_speed`: A multiplier applied to every song's scroll
		speed.
	`safe_window`: Amount of time notes can be hit before/after their
		actual time and still count as a hit, in ms.
	`key_bindings`: Key bindings mapping each key in `KEY` to their
		corresponding key in pyglet's `key` module. Multiple keys
		may also be specified in a list or tuple.
	"""
	scroll_speed: float
	safe_window: float
	key_bindings: t.Dict

	@staticmethod
	def validate(cfg: t.Dict) -> bool:
		return True # TODO: ye
