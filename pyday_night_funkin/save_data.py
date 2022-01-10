
from dataclasses import dataclass
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.enums import CONTROL


@dataclass
class SaveData():
	"""
	Stores game configuration. Some of these options make gameplay
	easier or harder.

	`scroll_speed`: A multiplier applied to every song's scroll
		speed.
	`safe_window`: Amount of time notes can be hit before/after their
		actual time and still count as a hit, in ms.
	`key_bindings`: Key bindings mapping each control input in `CONTROL`
		to its corresponding key in pyglet's `key` module. Multiple keys
		may also be specified in a list or tuple.
	"""
	scroll_speed: float
	safe_window: float
	key_bindings: t.Dict["CONTROL", t.Union[t.Sequence[int], int]]

	@staticmethod
	def validate(save_data: t.Dict) -> bool:
		return True # TODO: ye
