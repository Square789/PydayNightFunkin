
import typing as t

from loguru import logger
from pyglet import gl

from pyday_night_funkin.core.graphics import states
from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.pnf_batch import (
		PNFVertexList, PNFVertexDomain, GroupData
	)
	from pyday_night_funkin.core.graphics.pnf_group import PNFGroup


class _AnnotatedGroup:
	"""
	Small dataclass thing to hold some additional information about
	groups during draw list creation.
	"""

	def __init__(self, group: "PNFGroup", vertex_list: "PNFVertexList") -> None:
		self.group = group
		self.vertex_list = vertex_list

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} group={self.group} "
			f"vertex_list={self.vertex_list}>"
		)


class GroupChain:
	def __init__(self, groups: t.Sequence[_AnnotatedGroup]) -> None:
		self.groups = groups
		self.used_vertex_domains = {g.vertex_list.domain for g in groups}
		self.used_draw_modes = {g.vertex_list.draw_mode for g in groups}

	def _dump(self) -> str:
		r = f"<{self.__class__.__name__}\n"
		for c in self.groups:
			r += "  " + repr(c) + "\n"
		r += ">"
		return r


def visit(
	group: "PNFGroup", group_data: t.Dict["PNFGroup", "GroupData"]
) -> t.List[t.List["PNFGroup"]]:
	ret_chains = [[group]]
	if not group_data[group].children:
		return [[group]]

	# The only case where order can be dropped is if many childless
	# groups of same order are on the same level.
	sc = sorted(group_data[group].children)
	cur_order = sc[0].order
	cur_group_list: t.List["PNFGroup"] = []
	for child_group in sc:
		if child_group.order != cur_order:
			ret_chains.append(cur_group_list)
			cur_group_list = []
			cur_order = child_group.order

		for subchain in visit(child_group, group_data):
			cur_group_list.extend(subchain)

	if cur_group_list:
		ret_chains.append(cur_group_list)
	return ret_chains


class DrawListBuilder:
	def __init__(self, index_type: int) -> None:
		self.state = {type_: None for type_ in states.states}
		self._index_type = index_type
		self._index_type_size = GL_TYPE_SIZES[index_type]

	def build(self, top_groups, group_data):
		chains = []
		for group in sorted(top_groups):
			chains.extend(visit(group, group_data))

		# Le debug block
		print("=== Raw group chains:")
		print(*chains, sep="\n", end="\n\n")

		new_chains = []
		for chain in chains:
			groups = []
			for group in chain:
				vtxl = group_data[group].vertex_list
				if vtxl is not None:
					groups.append(_AnnotatedGroup(group, vtxl))
			if groups:
				new_chains.append(GroupChain(groups))

		# Le debug block
		print("=== Chains:")
		print(*new_chains, sep="\n", end="\n\n")

		return self.process_group_chains(new_chains)

	def process_group_chains(
		self,
		chains: t.Sequence[GroupChain],
	) -> t.Tuple[t.List[t.Callable[[], t.Any]], t.List[int]]:
		"""
		Takes a list of annotated groups and spits out a series of
		OpenGL calls and index arrays to render them.
		"""
		# TODO: This can certainly be optimized further by reordering groups.
		# Unfortunately, I am too stupid to figure out how.

		if not chains:
			return [], []

		draw_list = []
		state_wall = states.PseudoStateWall()
		indices = []
		# Vertex layout is dictated by vertex domain and a group's program.
		cur_vertex_layout = None
		cur_draw_mode = None
		cur_index_start = 0
		cur_index_run = 0

		for chain in chains:
			for agroup in chain.groups:
				# Extend the draw list with necessary state switch calls
				state_switches = state_wall.switch(agroup.group.states)

				n_vertex_layout = (agroup.vertex_list.domain, agroup.group.program.id)
				n_draw_mode = agroup.vertex_list.draw_mode

				# Any of these unfortunately force a new draw call
				if (
					state_switches or
					n_draw_mode != cur_draw_mode or
					cur_vertex_layout != n_vertex_layout
				):
					# Accumulate all indices so far into a draw call if there were any
					if cur_index_run > 0:
						def draw_elements(
							m=cur_draw_mode, c=cur_index_run, t=self._index_type, s=cur_index_start
						):
							gl.glDrawElements(m, c, t, s * self._index_type_size)
						draw_list.append(draw_elements)

						cur_index_start += cur_index_run
						cur_index_run = 0

					if cur_vertex_layout != n_vertex_layout:
						def bind_vao(d=agroup.vertex_list.domain, p=agroup.group.program):
							# TODO: Buffers store their data locally and need to be bound
							# to upload it.
							# This binding would always occurr in pyglet's default renderer
							# since it does not utilize VAOs, but needs to be
							# done explicitly here.
							# Maybe there's something that would be able to
							# get rid of these bind calls. (glMapNamedBufferRange?)
							for att in d.attributes.values():
								att.gl_buffer.bind()
							d.bind_vao(p)

						draw_list.append(bind_vao)
						cur_vertex_layout = n_vertex_layout

					cur_draw_mode = n_draw_mode
					draw_list.extend(state_switches)

				# Extend vertex indices
				indices.extend(agroup.vertex_list.indices)
				cur_index_run += len(agroup.vertex_list.indices)

		# Final draw call
		def final_draw_elements(
			m=cur_draw_mode, c=cur_index_run, t=self._index_type, s=cur_index_start,
			v=cur_vertex_layout[0]
		):
			gl.glDrawElements(m, c, t, s * self._index_type_size)
			v.unbind_vao()

		draw_list.append(final_draw_elements)

		return draw_list, indices
