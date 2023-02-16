
from collections import defaultdict
import typing as t
from weakref import WeakSet

from pyglet.gl import gl

from pyday_night_funkin.core.graphics.interfacer import PNFBatchInterfacer
from pyday_night_funkin.core.graphics.pnf_group import PNFGroup
from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain
from pyday_night_funkin.core.graphics.shared import (
	GL_TO_C_TYPE_MAP, GL_TYPE_SIZES, RE_VERTEX_FORMAT
)
from pyday_night_funkin.core.graphics.state import GLState
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject, RAMBackedBufferObject
from pyday_night_funkin.core.utils import dump_id

if t.TYPE_CHECKING:
	from .pnf_group import PNFGroup


_INDEX_TYPE = gl.GL_UNSIGNED_INT
_INDEX_TYPE_SIZE = GL_TYPE_SIZES[_INDEX_TYPE]


# NOTE: This is just a class with a list. May be useful for further
# work, may also turn out completely useless.
class GroupChain:
	__slots__ = ("groups",)

	def __init__(self, groups: t.Iterable["GroupData"]) -> None:
		self.groups = list(groups)
		# self.used_vertex_domains = {g.interfacer.domain for g in groups}
		# self.used_draw_modes = {g.interfacer.draw_mode for g in groups}

	def _dump(self) -> str:
		r = f"<{self.__class__.__name__}\n"
		for c in self.groups:
			r += "  " + repr(c) + "\n"
		r += ">"
		return r


class GroupData:
	"""
	GroupData is used to build a group tree by storing an interfacer
	and a group's children, which a group then maps to.
	"""
	__slots__ = ("interfacer", "state", "children", "group_chain")

	def __init__(
		self,
		state: t.Optional[GLState] = None,
		interfacer: t.Optional["PNFBatchInterfacer"] = None,
		children: t.Iterable["PNFGroup"] = (),
		group_chain: t.Optional[GroupChain] = None,
	) -> None:
		self.state = state
		self.interfacer = interfacer
		self.children = set(children)
		self.group_chain = group_chain

	@property
	def is_drawable(self):
		return self.interfacer is not None


class DrawList:
	"""
	A DrawList encompasses a group tree and hosts functionality to
	create optimized sprite drawing lists using index buffers.
	"""

	def __init__(self, name: t.Hashable) -> None:
		"""
		Initializes a DrawList. `name` is the name the owning batch
		registered the DrawList under.
		"""

		self.name = name

		self._dirty: bool = True
		self.funcs: t.List[t.Callable[[], t.Any]] = []
		"""
		List of functions to call in-order to draw everything that
		needs to be drawn.
		"""

		self._group_data: t.Dict["PNFGroup", "GroupData"] = defaultdict(GroupData)
		self._top_group = PNFGroup()
		self._group_data[self._top_group] = GroupData()
		self.index_buffer = RAMBackedBufferObject(
			gl.GL_ELEMENT_ARRAY_BUFFER, 0, gl.GL_DYNAMIC_DRAW, _INDEX_TYPE
		)

	def add_group(
		self,
		group: "PNFGroup",
		interfacer: t.Optional[PNFBatchInterfacer] = None,
		state: t.Optional[GLState] = None,
	) -> None:
		"""
		Add a group and all its parents to the group data
		registry and mark the draw list as dirty.
		If the group is already known, has no effect.
		"""
		if group in self._group_data:
			raise ValueError(f"Group {group!r} is already known in DrawList {self.name!r}.")

		fresh_group = group
		while True:
			tmp_parent = fresh_group.parent
			if tmp_parent is None:
				self._group_data[self._top_group].children.add(fresh_group)
				break
			if tmp_parent in self._group_data:
				self._group_data[tmp_parent].children.add(fresh_group)
				break
			self._group_data[tmp_parent].children.add(fresh_group)
			fresh_group = tmp_parent
	
		self._group_data[group].interfacer = interfacer
		self._group_data[group].state = state
		self._dirty = True

	def remove_group(self, group: "PNFGroup") -> None:
		"""
		Removes a group from this draw list's group tree.
		"""
		if self._group_data[group].children:
			raise ValueError(f"Drawable group {group!r} has children, can not remove.")

		self._delete_group(group)

	def _delete_group(self, group: "PNFGroup") -> None:
		"""
		Deletes a group from the group registry and marks the draw
		list as dirty. If a non-leaf node is deleted, it will leave
		a hole in the continuity of the group tree, so don't do that.
		"""
		if group.parent is not None and group.parent in self._group_data:
			self._group_data[group.parent].children.remove(group)
		self._group_data[self._top_group].children.discard(group)
		self._group_data.pop(group)

		self._dirty = True

	def _visit(self, group: "PNFGroup") -> t.Tuple[t.List[t.List["PNFGroup"]], bool]:
		"""
		Visits groups recursively.
		Returns a tuple of:
		0: A list of lists of drawable groups where all of the inner
		list's order between groups is irrelevant, but the order of
		outer lists must be kept.
		1: Whether the group visited was considered dangling/ had no
		bridges to a drawable group. This being `True` implies [0]
		being empty.
		"""
		chains = []
		group_intact = self._group_data[group].interfacer is not None
		if group_intact and self._group_data[group].interfacer._visible:
			# Don't draw invisible groups now
			chains.append([group])

		if group_intact and self._group_data[group].children:
			raise RuntimeError("Drawn group with children found.")

		if self._group_data[group].children:
			sc = sorted(self._group_data[group].children)
			cur_order = sc[0].order

			withheld_group_chains: t.List[t.List["PNFGroup"]] = []
			cur_group_chain: t.List["PNFGroup"] = []
			for child_group in sc:
				# If a child group breaks order (Booo!), add chain so far and reset
				if child_group.order != cur_order:
					if cur_group_chain:
						chains.append(cur_group_chain)
						cur_group_chain = []
					if withheld_group_chains:
						chains.extend(withheld_group_chains)
						withheld_group_chains = []
					cur_order = child_group.order

				subchains, cg_intact = self._visit(child_group)
				# This group may be a connecting group, consider it intact if the
				# children bridge to any drawable child group
				group_intact = group_intact or cg_intact or bool(subchains)
				if len(subchains) == 1:
					# This is an unordered child group. Neat, expand current chain with it
					# fully
					cur_group_chain.extend(subchains[0])
				else:
					# We want to add these last in order to be able to merge chains with
					# no order differences first.
					withheld_group_chains.extend(subchains)

			# Add last outstanding group list
			if cur_group_chain:
				chains.append(cur_group_chain)
			chains.extend(withheld_group_chains)

		# This group is dangling, delete it.
		if not group_intact:
			if chains:
				raise RuntimeError(
					"This should not have happened: Group was considered dangling "
					"but delivered chains!"
				)
			self._delete_group(group)

		return chains, group_intact

	def regenerate(self) -> t.Tuple[t.List[t.Callable[[], t.Any]], t.List[int]]:
		"""
		Rebuilds the draw list from the group tree.
		Returns a series of functions that - when called in order -
		will run through all necessary state mutations and draw
		calls to draw the scene which you want to draw and a list
		of indices the index buffer must contain at that point.
		"""
		chains = [
			GroupChain(self._group_data[g] for g in raw_chain)
			for raw_chain in self._visit(self._top_group)[0]
		]

		if not chains:
			return [], []

		# Below converts the group chains into GL calls.
		# TODO: This can certainly be optimized further by reordering
		# groups that share a GroupChain smartly in order to minimize
		# state switch cost.
		# Unfortunately, I am too stupid to figure out how, so just have
		# whatever this is. Smushes together common states, which is good
		# enough for the most part.
		for chain in chains:
			chain.groups.sort(key=lambda g: hash(g.state.part_set))

		# AT THIS POINT the chains can be flattened.

		cur_state = GLState.from_state_parts()
		draw_list = []
		indices = []
		# Vertex layout is dictated by vertex domain and a group's program.
		cur_vertex_layout = None
		cur_draw_mode = None
		cur_index_start = 0
		cur_index_run = 0

		for chain in chains:
			for group_data in chain.groups:
				# Get necessary state switch calls
				state_switches = cur_state.switch(group_data.state)
				cur_state = group_data.state

				new_vertex_layout = (group_data.interfacer.domain, group_data.state.program.id)
				new_draw_mode = group_data.interfacer.draw_mode

				# Any of these unfortunately force a new draw call
				if (
					state_switches or
					new_draw_mode != cur_draw_mode or
					cur_vertex_layout != new_vertex_layout
				):
					# Accumulate all indices so far into a draw call (if there were any)
					if cur_index_run > 0:
						def draw_elements(
							m=cur_draw_mode, c=cur_index_run, t=_INDEX_TYPE,
							s=cur_index_start*_INDEX_TYPE_SIZE
						):
							gl.glDrawElements(m, c, t, s)
						draw_list.append(draw_elements)

						cur_index_start += cur_index_run
						cur_index_run = 0

					if cur_vertex_layout != new_vertex_layout:
						def bind_vao(d=group_data.interfacer.domain, p=group_data.state.program):
							# Buffers store their data locally and need to be told to upload it.
							# Using a buffer that does direct glBufferSubData calls noticeably
							# slows down the freeplay scene, where a lot of vertex updates are
							# made each frame.
							for att in d.attributes.values():
								att.ensure()
							d.bind_vao(p, self.name)
							# This is the 4.1 compat branch, ibufs are not a part of VAOs.
							self.index_buffer.bind()

						draw_list.append(bind_vao)
						cur_vertex_layout = new_vertex_layout

					# Extend the draw list with the required state switch calls
					cur_draw_mode = new_draw_mode
					draw_list.extend(state_switches)

				# Extend vertex indices
				indices.extend(group_data.interfacer.indices)
				cur_index_run += len(group_data.interfacer.indices)

		if cur_index_run > 0:
			# Final draw call
			def final_draw_elements(
				m=cur_draw_mode, c=cur_index_run, t=_INDEX_TYPE,
				s=cur_index_start*_INDEX_TYPE_SIZE, d=cur_vertex_layout[0]
			):
				gl.glDrawElements(m, c, t, s)
				gl.glBindVertexArray(0)
			draw_list.append(final_draw_elements)

		return draw_list, indices

	def check_dirty(self) -> bool:
		"""
		Checks whether this draw list is dirty. If it is, regenerates
		it and returns `True`. Otherwise, returns `False`.
		"""
		if not self._dirty:
			return False

		funcs, indices = self.regenerate()
		self.funcs = funcs
		self.index_buffer.set_size_and_data_py(indices)
		self._dirty = False
		return True

	def draw(self) -> None:
		for f in self.funcs:
			f()

	def delete(self) -> None:
		"""
		Properly deletes the DrawList and frees up any OpenGL objects.
		"""
		self.index_buffer.delete()

		for gd in self._group_data.values():
			gd.children.clear() # probably makes cyclic reference breakup easier
		self._group_data = None
		# self._top_groups = None

	def dump_group_tree(self, gi: t.Iterable["PNFGroup"] = None, indent: int = 2) -> str:
		r = ""
		if gi is None:
			gi = [self._top_group]
		for g in gi:
			gd = self._group_data[g]
			r += f"{' ' * indent}Group {g}"
			if gd.interfacer is not None:
				r += (
					f", Interfacer {dump_id(gd.interfacer)}, state hash "
					f"{hash(gd.state.part_set)}"
				)
			r += "\n"
			if gd.children:
				r += self.dump_group_tree(self._group_data[g].children, indent + 2)

		return r

	def dump_debug_info(self) -> str:
		r = f"  Calls in draw list: {len(self.funcs)}\n"
		r += self.dump_group_tree()
		r += "Generated group chains:\n"
		r += "\n".join(map(repr, self._visit(self._top_group)[0]))
		return r


class PNFBatch:
	"""
	Poor attempt at turning pyglet's drawing system upside down.
	This batch is the core part of PydayNightFunkin's rendering
	backend, works in conjunction with PNFGroups and tries
	to minimize the amount of OpenGL calls made during a draw cycle
	while facing many drawables of a strictly different order.
	Unlike pyglet's batch, it is able to construct multiple draw
	lists, aiding in creating a HaxeFlixel-like camera system.
	"""

	def __init__(self) -> None:
		self._draw_lists: t.Dict[t.Hashable, DrawList] = {}
		self._vertex_domains: t.Dict["frozenset[str]", "PNFVertexDomain"] = {}
		self._interfacers: "WeakSet[PNFBatchInterfacer]" = WeakSet()
		"""Stores the interfacers this batch owns."""

	def _get_draw_list(self, name: t.Hashable) -> DrawList:
		"""
		Gets a draw list, creating it if it did not exist.
		"""
		if name not in self._draw_lists:
			self._draw_lists[name] = DrawList(name)
		return self._draw_lists[name]

	def _get_vertex_domain(self, attr_bundle: t.Iterable[str]) -> PNFVertexDomain:
		"""
		Gets an existing or newly created vertexdomain for the given
		vertex attribute bundle.
		"""
		attr_bundle = frozenset(attr_bundle)
		if attr_bundle not in self._vertex_domains:
			self._vertex_domains[attr_bundle] = PNFVertexDomain(attr_bundle)
		return self._vertex_domains[attr_bundle]

	def add(
		self,
		size: int,
		draw_mode: int,
		group: "PNFGroup",
		states: t.Dict[t.Hashable, GLState],
		*data: t.Union[str, t.Tuple[str, t.Any]],
	) -> PNFBatchInterfacer:
		# NOTE: This is somewhat iffy, but on the other hand allowing non-
		# indexed stuff would mean even more frequent switches between
		# draw calls.
		# In this project, most drawables are indexed sprites anyways.
		return self.add_indexed(size, draw_mode, group, [*range(size)], states, *data)

	def add_indexed(
		self,
		size: int,
		draw_mode: int,
		group: "PNFGroup",
		indices: t.Sequence[int],
		states: t.Dict[t.Hashable, GLState],
		*data: t.Tuple[str, t.Optional[t.Collection]],
	) -> PNFBatchInterfacer:
		domain = self._get_vertex_domain(x[0] for x in data)
		start = domain.allocate(size)
		interfacer = PNFBatchInterfacer(
			domain, start, size, draw_mode, indices, self, group
		)
		self._introduce_interfacer(interfacer, states)

		# Set initial data
		for att_str, ini_data in data:
			if ini_data is None:
				continue
			interfacer.set_data(RE_VERTEX_FORMAT.match(att_str)[1], ini_data)

		return interfacer

	def draw(self, draw_list_name: t.Hashable):
		"""
		Draws the given draw list.
		"""
		draw_list = self._draw_lists[draw_list_name]
		draw_list.check_dirty()
		draw_list.draw()

	def _introduce_interfacer(
		self,
		interfacer: "PNFBatchInterfacer",
		states: t.Dict[t.Hashable, GLState],
	) -> None:
		"""
		Introduces an interfacer and the draw lists its vertices
		should occupy to the batch's draw lists.
		"""
		interfacer.set_states(states)
		self._interfacers.add(interfacer)

	def _remove_interfacer(self, interfacer: "PNFBatchInterfacer") -> None:
		"""
		To be called when an interfacer leaves this batch.
		Removes the interfacer from all draw lists.
		"""
		if interfacer not in self._interfacers:
			return

		for dl_id in interfacer._draw_lists:
			self.remove_group(dl_id, interfacer._group)
		self._interfacers.remove(interfacer)

	def add_group(
		self,
		draw_list: t.Hashable,
		interfacer: "PNFBatchInterfacer",
		group: "PNFGroup",
		state: GLState,
	) -> None:
		"""
		Adds a group alongside with its owning interfacer and the state
		it should be drawn under to the given draw list, which is newly
		created when not present.
		"""
		self._get_draw_list(draw_list).add_group(group, interfacer, state)

	def remove_group(self, draw_list: t.Hashable, group: "PNFGroup") -> None:
		"""
		Removes the given group from the given draw list's group tree.
		The draw list must exist.
		"""
		self._draw_lists[draw_list].remove_group(group)

	def delete(self) -> None:
		"""
		Deletes all vertex domain's buffers this batch is using,
		as well as the draw list's index buffers.
		This will break all interfacers and draw lists owned by this
		batch, so be sure they are not going to be used anymore.
		"""
		for dom in self._vertex_domains.values():
			dom.delete()
		for dl in self._draw_lists.values():
			dl.delete()

	def dump_debug_info(self) -> str:
		r = f"Interfacers created and alive: {len(self._interfacers)}"
		r += f"\nDraw list info:"
		for dl_name, dl in self._draw_lists.items():
			r += f"\nDraw list {dl_name}:\n"
			r += dl.dump_debug_info()

		r += "\nVertex Domain info:"
		for key, vtxd in self._vertex_domains.items():
			r += f"\n{sorted(key)}\n"
			for name, att in vtxd.attributes.items():
				r += f"  {name}: {att}\n"
				arr = att.get_data_elements(0, 16)
				r += f"  First 16 elements: {arr[:]}\n    [{arr}]\n"

		return r


_fake_batch = PNFBatch()
def get_default_batch():
	return _fake_batch
