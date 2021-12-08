
import typing as t

from loguru import logger

from pyday_night_funkin.core.graphics import states

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics import PNFGroup


class GroupChain:
	def __init__(self, groups: t.Sequence["PNFGroup"], static: bool = False) -> None:
		self.groups = groups
		self.static = static

	def _dump(self) -> str:
		r = f"<{self.__class__.__name__} [{'static' if self.static else 'sortable'}] \n"
		for c in self.groups:
			r += "  " + repr(c) + "\n"
		r += ">"
		return r


class DrawListBuilder:
	def __init__(self) -> None:
		self.state = {type_: None for type_ in states.states}

	def build(self, top_groups, group_data):
		self.draw_list = []
		self.group_data = group_data

		chains = []
		for group in sorted(top_groups):
			chains.extend(self.visit(group))

		del self.group_data

		for chain in chains:
			print(chain._dump())

		return self.draw_list

	def visit(self, group, n=0) -> None:
		logger.debug(("    " * n) + f"Yooo {group}")
		if self.group_data[group].vertex_domain is None:
			logger.debug(("    " * n) + " (No vertex domain)")

		ret_chains = [GroupChain((group, ))]
		if not self.group_data[group].children:
			return ret_chains

		sc = sorted(self.group_data[group].children)
		cur_order = sc[0].order
		cur_chain_list = []
		for child_group in sc:
			if child_group.order != cur_order:
				ret_chains.append(GroupChain(cur_chain_list))
				cur_chain_list = []
				cur_order = child_group.order

			cur_chain_list.extend(self.visit(child_group, n + 1))

		if cur_chain_list:
			ret_chains.append(GroupChain(cur_chain_list))
		return ret_chains
