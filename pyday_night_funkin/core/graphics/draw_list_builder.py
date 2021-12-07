
import typing as t

from loguru import logger

from pyday_night_funkin.core.graphics import states

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics import PNFGroup


class DrawListBuilder:
	def __init__(self) -> None:
		self.state = {type_: None for type_ in states.states}

	def build(self, top_groups, group_data):
		self.draw_list = []
		self.group_data = group_data

		for group in sorted(top_groups):
			self.visit(group)

		del self.group_data

		return self.draw_list

	def visit(self, group, n: int = 0) -> None:
		logger.debug((" " * n) + f"Yooo {group}")

		for sub_group in sorted(self.group_data[group].children):
			self.visit(sub_group, n + 1)
