
from collections import defaultdict
import typing as t

from pyday_night_funkin.enums import CONTROL

class RawKeyHandler:
	def __init__(self) -> None:
		self._just_pressed_keys: t.Set[int] = set()
		self._pressed_keys: t.Set[int] = set()

	def on_key_press(self, key_sym: int, modifiers: int) -> None:
		self._just_pressed_keys.add(key_sym)
		self._pressed_keys.add(key_sym)

	def on_key_release(self, key_sym: int, modifiers: int) -> None:
		self._just_pressed_keys.discard(key_sym)
		self._pressed_keys.discard(key_sym)

	def post_update(self) -> None:
		self._just_pressed_keys.clear()

	def just_pressed(self, key: int) -> bool:
		return key in self._just_pressed_keys

	def pressed(self, key: int) -> bool:
		"""
		Returns whether a key is pressed/being held down.
		"""
		return key in self._pressed_keys

	__getitem__ = pressed


class KeyHandler:
	"""
	Class to manage key presses by mapping them to controls.
	"""

	def __init__(self, key_bindings: t.Dict[CONTROL, t.Sequence[int]]):
		"""
		# TODO Le doc
		"""
		self.key_bindings = key_bindings
		self.control_activators: t.Dict[CONTROL, t.Set[int]] = {
			k: set() for k in key_bindings.keys()
		}
		self._just_pressed_controls: t.Set[CONTROL] = set()

		_key_to_control_map = defaultdict(list)
		for ctrl, keys in key_bindings.items():
			for key in keys:
				_key_to_control_map[key].append(ctrl)
		self._key_to_control_map = dict(_key_to_control_map)

	def on_key_press(self, key_sym: int, modifiers: int) -> None:
		if key_sym not in self._key_to_control_map:
			return
		for control in self._key_to_control_map[key_sym]:
			pressed_before = self.pressed(control)
			self.control_activators[control].add(key_sym)
			if not pressed_before:
				self._just_pressed_controls.add(control)

	def on_key_release(self, key_sym: int, modifiers: int) -> None:
		if key_sym not in self._key_to_control_map:
			return
		for control in self._key_to_control_map[key_sym]:
			self.control_activators[control].discard(key_sym)
			if not self.pressed(control):
				self._just_pressed_controls.discard(control)

	def just_pressed(self, control: CONTROL) -> bool:
		"""
		Returns whether a control was "just pressed". This will be False
		for an unpressed control, True if this is the first time the
		method was called on a held control and False for all subsequent
		calls as long as the control is not fully released by deactivation
		of all its triggering keys and pressed again.
		"""
		return control in self._just_pressed_controls

	def pressed(self, control: CONTROL) -> bool:
		"""
		Returns whether a control is pressed/being held down.
		"""
		return bool(self.control_activators[control])

	def post_update(self) -> None:
		"""
		This method will remove the "just pressed" association of all
		pressed controls where it may exist.
		Should never be called by user code, this will be managed
		by the game loop.
		"""
		self._just_pressed_controls.clear()

	__getitem__ = pressed
