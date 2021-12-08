
import typing as t

from loguru import logger

from pyday_night_funkin.core.graphics import states

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.pnf_batch import PNFVertexList
	from pyday_night_funkin.core.graphics.pnf_group import PNFGroup


# class GroupChain:
# 	def __init__(self, groups: t.Sequence["PNFGroup"], static: bool = False) -> None:
# 		self.groups = groups
# 		self.static = static

# 	def _dump(self) -> str:
# 		r = f"<{self.__class__.__name__} [{'static' if self.static else 'sortable'}] \n"
# 		for c in self.groups:
# 			r += "  " + repr(c) + "\n"
# 		r += ">"
# 		return r


class _AnnotatedGroup:
	"""
	Small dataclass thing to hold some additional information about
	groups during draw list creation.
	"""

	def __init__(self, group, abs_order, vertex_list: "PNFVertexList") -> None:
		self.group = group
		self.abs_order = abs_order
		self.vertex_list = vertex_list
		self.vertex_domain = vertex_list.vtxd

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} group={self.group} abs_order={self.abs_order} "
			f"vertex_list={self.vertex_list}>"
		)


class DrawListBuilder:
	def __init__(self) -> None:
		self.state = {type_: None for type_ in states.states}

	def build(self, top_groups, group_data):
		self.group_data = group_data

		chains = []
		for group in sorted(top_groups):
			chains.extend(self.visit(group))

		ann_groups = []
		abs_order = 0
		for chain in chains:
			appended = False
			for group in chain:
				vtxl = group_data[group].vertex_list
				if vtxl is not None:
					ann_groups.append(_AnnotatedGroup(group, abs_order, vtxl))
					appended = True
			if appended:
				abs_order += 1

		del self.group_data

		# Le debug block
		print("=== Raw group chains:")
		print(*chains, sep="\n", end="\n\n")
		print("=== Annotated groups:")
		print(*ann_groups, sep="\n", end="\n\n")

		return self.process_group_chains(chains)

	def process_group_chains(self, chains):
		"""
		Cleverness!!!
		"""
		draw_list = []
		state = states.State()

		return draw_list

	def visit(self, group):
		ret_chains = [[group]]
		if not self.group_data[group].children:
			# Don't nest childless groups in another GroupChain.
			# I think this is right. Maybe. Hopefully.
			return [group]

		sc = sorted(self.group_data[group].children)
		cur_order = sc[0].order
		cur_group_list = []
		for child_group in sc:
			if child_group.order != cur_order:
				ret_chains.append(cur_group_list)
				cur_group_list = []
				cur_order = child_group.order

			cur_group_list.extend(self.visit(child_group))

		if cur_group_list:
			ret_chains.append(cur_group_list)
		return ret_chains
