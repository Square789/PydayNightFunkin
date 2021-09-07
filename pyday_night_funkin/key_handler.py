
from collections import defaultdict
import typing as t

from pyday_night_funkin.config import CONTROL

# TODO: There are most definitely bugs here where a control is
# considered released reset when any of its associated keys are
# released and not all of them.

class KeyHandler():
	"""
	Class to manage key presses.
	"""
	def __init__(self, key_bindings: t.Dict[CONTROL, int]):
		"""
		# TODO Le doc
		"""
		self.key_bindings = key_bindings
		# 0: Whether key is being held
		# 1: Whether key just got pressed (reset once just_pressed) is queried
		self.control_states = {k: [False, False] for k in key_bindings.keys()}
		_key_to_control_map = defaultdict(list)
		for k, v in key_bindings.items():
			if isinstance(v, (tuple, list)):
				for vv in v:
					_key_to_control_map[vv].append(k)
			else:
				_key_to_control_map[v].append(k)
		self._key_to_control_map = dict(_key_to_control_map)

	def on_key_press(self, key_sym: int, modifiers: int) -> None:
		if key_sym not in self._key_to_control_map:
			return
		for control in self._key_to_control_map[key_sym]:
			self.control_states[control][0] = True
			self.control_states[control][1] = True

	def on_key_release(self, key_sym: int, modifiers: int) -> None:
		if key_sym not in self._key_to_control_map:
			return
		for control in self._key_to_control_map[key_sym]:
			self.control_states[control][0] = False
			self.control_states[control][1] = False

	def just_pressed(self, control: CONTROL) -> bool:
		"""
		Returns whether a control was "just pressed". This will be False
		for an unpressed control, True if this is the first time the
		method was called on a held control and False for all subsequent
		calls as long as the control is not released and pressed again.
		"""
		if not self.pressed(control):
			return False
		retv = self.control_states[control][1]
		self.control_states[control][1] = False
		return retv

	def pressed(self, control: CONTROL) -> bool:
		"""
		Returns whether a control is pressed/being held down.
		"""
		return self.control_states[control][0]

	def __getitem__(self, control: CONTROL) -> bool:
		return self.pressed(control)
