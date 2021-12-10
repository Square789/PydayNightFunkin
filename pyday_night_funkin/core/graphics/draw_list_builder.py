
from ctypes import create_unicode_buffer
import typing as t

from loguru import logger
from pyglet import gl

from pyday_night_funkin.core.graphics import states

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.graphics.pnf_batch import PNFVertexList, PNFVertexDomain
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
		self.used_vertex_domains = {g.vertex_list.vtxd for g in groups}
		self.used_draw_modes = {g.vertex_list.draw_mode for g in groups}

	def _dump(self) -> str:
		r = f"<{self.__class__.__name__}\n"
		for c in self.groups:
			r += "  " + repr(c) + "\n"
		r += ">"
		return r


def visit(group, group_data):
	ret_chains = [[group]]
	if not group_data[group].children:
		# Don't nest childless groups in another GroupChain.
		# I think this is right. Maybe. Hopefully.
		return [group]

	sc = sorted(group_data[group].children)
	cur_order = sc[0].order
	cur_group_list = []
	for child_group in sc:
		if child_group.order != cur_order:
			ret_chains.append(cur_group_list)
			cur_group_list = []
			cur_order = child_group.order

		cur_group_list.extend(visit(child_group, group_data))

	if cur_group_list:
		ret_chains.append(cur_group_list)
	return ret_chains


class DrawListBuilder:
	def __init__(self) -> None:
		self.state = {type_: None for type_ in states.states}
		self._index_type = gl.GL_UNSIGNED_INT

	def build(self, top_groups, group_data):
		chains = []
		for group in sorted(top_groups):
			chains.extend(visit(group, group_data))

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
		print("=== Raw group chains:")
		print(*chains, sep="\n", end="\n\n")
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
		# TODO: This can be optimized further.
		# Unfortunately, I am too stupid to figure out how.

		if not chains:
			return []

		draw_list = []
		state_wall = states.PseudoStateWall()
		indices = []
		# Vertex layout is dictated by vertex domain and a group's program.
		cur_vertex_layout = None
		cur_draw_mode = None
		cur_index_start = 0
		cur_index_run = 0

		# Things that WILL require another draw call:
		# VertexDomain switches
		# Draw mode switches
		# VertexDomain change is much more serious than using a different draw mode!

		for chain in chains:
			for agroup in chain.groups:
				n_vertex_layout = (agroup.vertex_list.vtxd, agroup.group.program.id)
				n_draw_mode = agroup.vertex_list.draw_mode

				# This unfortunately forces a new draw call
				if (n_draw_mode != cur_draw_mode or cur_vertex_layout != n_vertex_layout):
					logger.info(f"New draw call @ {agroup}")
					if cur_vertex_layout != n_vertex_layout:
						def bind_vao(d=agroup.vertex_list.vtxd, p=agroup.group.program):
							d.bind_vao(p)
						draw_list.append(bind_vao)

					# Accumulate all indices so far into a draw call if there were any
					# (Should just catch the first group)
					if cur_index_run > 0:
						def draw_elements(
							m=cur_draw_mode, c=cur_index_run, t=self._index_type, s=cur_index_start
						):
							gl.glDrawElements(m, c, t, s)
						draw_list.append(draw_elements)
						cur_index_start += cur_index_run
						cur_index_run = 0

					cur_vertex_layout = n_vertex_layout
					cur_draw_mode = n_draw_mode

				# Extend the draw list with necessary state switch calls
				draw_list.extend(state_wall.switch(agroup.group.states))
				# Extend vertex indices
				indices.extend(agroup.vertex_list.indices)
				cur_index_run += len(agroup.vertex_list.indices)

		# Final draw call
		def final_draw_elements(
			m=cur_draw_mode, c=cur_index_run, t=self._index_type, s=cur_index_start
		):
			gl.glDrawElements(m, c, t, s)
		draw_list.append(final_draw_elements)

		return draw_list, indices
