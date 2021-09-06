
from collections import defaultdict
import typing as t

from pyglet.window import key

from pyday_night_funkin.config import KEY


class KeyHandler():
	"""
	Class to manage key presses.
	"""
	def __init__(self, key_bindings: t.Dict[KEY, int]):
		"""
		# TODO Le doc
		"""
		self.key_bindings = key_bindings
		# 0: Whether key is being held
		# 1: Whether key just got pressed (reset once just_pressed) is queried
		self.key_states = {k: [False, False] for k in key_bindings.keys()}
		_inverted_keys = defaultdict(list)
		for k, v in key_bindings.items():
			if isinstance(v, (tuple, list)):
				for vv in v:
					_inverted_keys[vv].append(k)
			else:
				_inverted_keys[v].append(k)
		self._pyglet_to_game_key_map = dict(_inverted_keys)

	def on_key_press(self, key_sym: int, modifiers: int) -> None:
		if key_sym not in self._pyglet_to_game_key_map:
			return
		for game_key in self._pyglet_to_game_key_map[key_sym]:
			self.key_states[game_key][0] = True
			self.key_states[game_key][1] = True

	def on_key_release(self, key_sym: int, modifiers: int) -> None:
		if key_sym not in self._pyglet_to_game_key_map:
			return
		for game_key in self._pyglet_to_game_key_map[key_sym]:
			self.key_states[game_key][0] = False
			self.key_states[game_key][1] = False

	def just_pressed(self, key: KEY) -> bool:
		"""
		Returns whether a key was "just pressed". This will be False
		for an unpressed key, True if this is the first time the
		method was called on a held key and False for all subsequent
		calls as long as the key is not released and pressed again.
		"""
		if not self.pressed(key):
			return False
		retv = self.key_states[key][1]
		self.key_states[key][1] = False
		return retv

	def pressed(self, key: KEY) -> bool:
		"""
		Returns whether a key is pressed/being held down.
		"""
		return self.key_states[key][0]

	def __getitem__(self, key: KEY) -> bool:
		return self.pressed(key)
