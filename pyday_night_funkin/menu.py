
import typing as t

from pyday_night_funkin.core.key_handler import KeyHandler
from pyday_night_funkin.config import CONTROL


class Menu:
	"""
	Cheap menu class to stash away commonly repeated
	"up-down-to-switch-through-a-menu" functionality.
	"""

	def __init__(
		self,
		key_handler: "KeyHandler",
		item_count: int,
		on_select: t.Optional[t.Callable[[int, bool], t.Any]] = None,
		on_confirm: t.Optional[t.Callable[[int, bool], t.Any]] = None,
		ini_selection_index: int = 0,
		fwd_control: CONTROL = CONTROL.DOWN,
		bkwd_control: CONTROL = CONTROL.UP,
	) -> None:
		"""
		Initializes a menu.

		On initialization, `on_select` will be called for each item,
		where the second boolean parameter corresponds to whether the
		first parameter is the menu's selected index.

		:param key_handler: The `KeyHandler` to use for checking
			controls.
		:param item_count: The amount of items in the menu.
		:param on_select: Function to be called whenever the selection
			changes. It takes two arguments, an index and a bool. The
			function will be called twice whenever the selection
			changes, once for the deselected index with `False`, and
			once for the newly selected index with `True`.
			Note that the menu's `selection_index` attribute is changed
			from old to new inbetween these two calls.
		:param on_confirm: Similar to `on_select`, however it will be
			called whenever the confirmation control is hit,
			`item_count` times for each index. One of these calls will
			be passed `True` for the chosen index, the others `False`.
		:param ini_selection_index: The initial selection index.
			0 per default.
		:param fwd_control: Control to scroll the menu down. This will
			be checked via the key handler's `just_pressed` method each
			`update` call.
		:param bkwd_control: Same as `fwd_control`, just in the other
			direction.
		"""
		if ini_selection_index < 0 or ini_selection_index >= item_count:
			raise ValueError("Invalid selection index!")
		if item_count <= 0:
			raise ValueError("Invalid item count!")
		self.selection_index = ini_selection_index
		self.choice_made = False
		self.key_handler = key_handler
		self.item_count = item_count
		self.on_select = on_select or (lambda *_: None)
		self.on_confirm = on_confirm or (lambda *_: None)

		self._fwd_control = fwd_control
		self._bkwd_control = bkwd_control

		for i in range(item_count):
			self.on_select(i, i == ini_selection_index)

	def _change_item(self, by: int) -> None:
		self._set_selection_index((self.selection_index + by) % self.item_count)

	def _set_selection_index(self, new: int) -> None:
		"""
		Sets a new selection index. Does not perform bounds checking,
		if you funnel a faulty value in here, too bad!
		"""
		if self.selection_index == new:
			return

		self.on_select(self.selection_index, False)
		self.selection_index = new
		self.on_select(self.selection_index, True)

	def set_item_count(self, new_item_count: int) -> bool:
		"""
		Sets a new item count. Must be greater than zero.
		Sets the selection index to `new_item_count - 1` if it would
		be out of range after the change. Returns whether the
		selection index was modified.
		"""
		if new_item_count <= 0:
			raise ValueError("Can't have a menu with less than one item!")

		self.item_count = new_item_count
		if self.selection_index >= new_item_count:
			self._set_selection_index(new_item_count - 1)
			return True
		return False

	def update(self) -> None:
		"""
		Updates the menu. Should be called each frame.
		Will run registered callbacks and 
		When `CONTROL.ENTER` is pressed, `choice_made` is set to
		`True`.
		While `choice_made` is truthy, the menu will immediatedly
		return from this method and ignore all input.
		"""
		if self.choice_made:
			return False

		kh = self.key_handler

		if kh.just_pressed(self._bkwd_control):
			self._change_item(-1)

		if kh.just_pressed(self._fwd_control):
			self._change_item(1)

		if kh.just_pressed(CONTROL.ENTER):
			self.choice_made = True
			for i in range(self.item_count):
				self.on_confirm(i, i == self.selection_index)
