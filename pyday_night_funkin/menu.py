import typing as t

from pyday_night_funkin.core.key_handler import KeyHandler
from pyday_night_funkin.config import CONTROL


class Menu:
	"""
	Small and ugly class to stash away commonly repeated
	"up-down-to-switch-through-a-menu" functionality.
	"""

	def __init__(self, key_handler: "KeyHandler", item_count: int) -> None:
		if item_count <= 0:
			raise ValueError("Can't have a menu with less than one item!")

		self.selection_index = 0
		self.choice_made = False
		self.key_handler = key_handler
		self.item_count = item_count

	def _change_item(self, by: int) -> None:
		self.selection_index += by
		self.selection_index %= self.item_count

	def update(self) -> bool:
		"""
		Updates the menu. Should be called each frame.
		If a selection change occurred, will return `True`,
		where the new selected index can be retrieved from
		`selection_idex`.
		If a confirmation occurred, will set `choice_made` to `True`.
		While `choice_made` is `True`, the menu will immediatedly
		return `False` from this method no matter what.
		"""
		if self.choice_made:
			return False

		kh = self.key_handler

		selection_changed = False
		if kh.just_pressed(CONTROL.UP) and self.item_count > 1:
			selection_changed = True
			self._change_item(-1)

		if kh.just_pressed(CONTROL.DOWN) and self.item_count > 1:
			selection_changed = True
			self._change_item(1)

		if kh.just_pressed(CONTROL.ENTER):
			self.choice_made = True

		return selection_changed
