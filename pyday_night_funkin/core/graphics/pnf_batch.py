
from collections import defaultdict
from enum import IntEnum
from time import perf_counter
import typing as t
from weakref import WeakSet

from pyglet.gl import gl

from pyday_night_funkin.core.graphics.interfacer import PNFBatchInterfacer
from pyday_night_funkin.core.graphics.pnf_group import PNFGroup
from pyday_night_funkin.core.graphics.pnf_vertex_domain import PNFVertexDomain
from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES, RE_VERTEX_FORMAT
from pyday_night_funkin.core.graphics.state import GLState
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject, RAMBackedBufferObject
from pyday_night_funkin.core.utils import dump_id, linked_list_iter

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
		r = [f"<{self.__class__.__name__}\n"]
		for c in self.groups:
			r.append("  " + repr(c) + "\n")
		r.append(">")
		return "".join(r)


class DrawListSegment:
	"""
	A DrawListSegment is a part inside a batch's draw list that
	contains the state setup required for a single draw call
	and then that draw call.
	Contains backreferences to the provoking groups, making
	insertions and splitting them possible.
	"""

	def __init__(
		self,
		funcs: t.Sequence[t.Callable[[], t.Any]],
		ibuf_start: int,
		ibuf_range: int,
	) -> None:
		self.funcs: t.Sequence[t.Callable[[], t.Any]] = funcs
		"""
		The series of functions that need to be called in order to
		render this segment's drawables.
		"""

		self._index_buffer_start: int = ibuf_start
		self._index_buffer_range: int = ibuf_range

		self._provoking_groups: t.Sequence["PNFGroup"] = []

		self._prev: t.Optional["DrawListSegment"] = None
		self._next: t.Optional["DrawListSegment"] = None

		# self.transcends_order: bool = False
		# """
		# Whether this draw list segment contains drawables that have to
		# be ordered, taking advantage of the fact that these all
		# shared the same state.
		# """


class ClusterInfo:
	# __slots__ = ("root", "operations", "groups") #, "dirty_groups")

	def __init__(self) -> None:
		self.root: "PNFGroup" = None
		self.operations: int = 0
		self.groups: t.Set["PNFGroup"] = set()
		self.r: str = ""
		"""Reason: Debug. Remove once the grafix_v3 branch is good."""
		# self.dirty_groups: t.Set["PNFGroup"] = set()

	def __repr__(self) -> None:
		return (
			f"<{self.__class__.__name__}(root={self.root!r}, operations={self.operations!r}, "
			f"~gc={len(self.groups)}, r={self.r}) at {dump_id(self)}>"
		)


class GroupData:
	"""
	GroupData is used to build a group tree by storing an interfacer,
	a group's children and many other things, which a group then maps
	to.
	"""
	# NOTE: Drawable groups may never have children!

	__slots__ = (
		"interfacer", "state", "children", "pending_operation", "draw_list_segment"
	)

	def __init__(self) -> None:
		self.state: t.Optional[GLState] = None
		"""The GLState the group must be rendered under."""

		self.interfacer: t.Optional[PNFBatchInterfacer] = None
		"""
		The interfacer that was created with the introduction of this
		group.
		"""

		self.draw_list_segment: t.Optional[DrawListSegment] = None
		"""
		The draw list segment that is responsible for drawing this
		group or the first of this group's children (that is, if you
		were to walk down keeping to the left/lowest order until
		reaching a child group). May be None in case this group has
		no drawable children or it has not been solidified in the draw
		list yet.
		"""

		self.children: t.Set["PNFGroup"] = set()
		"""Children of the group."""

		self.pending_operation: int = 0
		"""
		An operation this group is waiting for. If this is not 0, the
		group must be present in its draw list's `_dirty_groups`set.
		"""


GROUP_OPERATION_ADD = 1
GROUP_OPERATION_DEL = 2
GROUP_OPERATION_MOD = 4


class DrawList:
	"""
	A DrawList encompasses a group tree and hosts functionality to
	create an optimized series of draw calls using index buffers.
	"""

	def __init__(self, name: t.Hashable) -> None:
		"""
		Initializes a DrawList. `name` is the name the owning batch
		registered the DrawList under.
		"""

		self.name = name

		self._dirty_groups: t.Set["PNFGroup"] = set()
		"""
		Contains groups which have to be added, removed or modfiied in
		respect to the draw list.
		Only groups whose group data's `pending_operation` attribute is
		not zero must be in here.
		This may contain undrawable intermediate groups if they have
		just been introduced via addition of a drawable child or marked
		for deletion.
		"""

		self._draw_list: t.Optional[DrawListSegment] = None
		"""
		Linked list containing the draw list segments required for
		rendering and more.
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
		Adds a group and all its parents to the group data registry and
		# TODO yeah, what does it do, exactly?
		"""
		group_data = self._group_data
		if group in group_data:
			# TODO: it should be allowed to re-add a group pending deletion,
			# converting it into a modify operation
			raise ValueError(f"Group {group!r} is already known in DrawList {self.name!r}. [FIXME]")

		fresh_group = group
		hook_group = None
		while True:
			group_data[fresh_group].pending_operation = GROUP_OPERATION_ADD
			self._dirty_groups.add(fresh_group)
			tmp_parent = fresh_group.parent
			if tmp_parent is None:
				hook_group = self._top_group
				break
			if tmp_parent in group_data:
				hook_group = tmp_parent
				break
			group_data[tmp_parent].children.add(fresh_group)
			fresh_group = tmp_parent

		# hook_group is the group the complete strand of groups has
		# been added to.
		# self._dirty_groups.add(hook_group)
		group_data[hook_group].children.add(fresh_group)

		# finally, make the new group itself drawable
		group_data[group].interfacer = interfacer
		group_data[group].state = state

	def remove_group(self, group: "PNFGroup") -> None:
		"""
		Removes a group from this draw list's group tree.
		"""
		if self._group_data[group].children:
			raise ValueError(f"Drawable group {group!r} has children, can not remove.")

		self._delete_group(group)

	def _delete_group(self, group: "PNFGroup") -> None:
		"""
		Deletes a group from the group registry.
		If a non-leaf node is deleted, it will leave a hole in the
		continuity of the group tree, so don't do that.
		"""
		if group is self._top_group:
			raise RuntimeError("Can not delete top group.")

		pgr = self._top_group if group.parent is None else group.parent
		if self._group_data[group].pending_operation == GROUP_OPERATION_ADD:
			# lucky case, it's not been registered yet, so we can throw it out immediatedly
			self._group_data[pgr].children.remove(group)
			self._dirty_groups.remove(group)
			self._group_data.pop(group)
		else:
			# TODO??? remove here???
			# self._group_data[pgr].children.remove(group)
			self._group_data[group].pending_operation = GROUP_OPERATION_DEL
			self._dirty_groups.add(group)

	def _remove_group_direct(self, group: "PNFGroup") -> None:
		"""
		Directly removes all of a group's possible presence in the
		group data tree.
		"""
		pgr = self._top_group if group.parent is None else group.parent
		self._group_data[pgr].children.remove(group)
		if (dls := self._group_data[group].draw_list_segment) is not None:
			dls._provoking_groups.remove(group)
		self._dirty_groups.discard(group)
		self._group_data.pop(group)

	def modify_group(self, group: "PNFGroup", new_state: t.Optional[GLState] = None) -> None:
		"""
		Tells the draw list to 5whfnP4Vd3s an existing group,
		possibly with a new state. Realistically, if the state is not
		given, this is to be understood as a visibility change of the
		group's interfacer
		"""
		if group not in self._group_data:
			raise RuntimeError(f"Can not modify unknown group {group!r}")
		self._dirty_groups.add(group)
		if self._group_data[group].pending_operation != GROUP_OPERATION_ADD:
			# Only set for groups that already are solidified in the draw list.
			# Groups that are deleted are saved this way.
			# Groups that are to be added would have been processed anyways, but must be
			# introduced to the regeneration method with the ADD state.
			self._group_data[group].pending_operation = GROUP_OPERATION_MOD
		if new_state is not None:
			self._group_data[group].state = new_state

	def _visit(
		self,
		group: "PNFGroup",
		children_override: t.Optional[t.Sequence["PNFGroup"]] = None,
	) -> t.Tuple[t.List[t.List["PNFGroup"]], bool]:
		"""
		Visits groups recursively and builds an outline for their
		drawing process.
		Returns a tuple of:
		0: A list of lists of drawable groups where all of the inner
		list's order between groups is irrelevant, but the order of
		outer lists must be kept.
		1: Whether the group visited was considered dangling and has
		been deleted from the group tree. (Alongside all of its
		children, if any.). This being true implies [0] being empty.
		"""
		chains: t.List[t.List["PNFGroup"]] = []
		group_data = self._group_data[group]
		group_intact = (
			group_data.interfacer is not None and
			group_data.pending_operation != GROUP_OPERATION_DEL
		)
		if group_intact and group_data.interfacer._visible:
			# Don't draw invisible groups now
			chains.append([group])

		if group_intact and group_data.children:
			raise RuntimeError("Drawn group with children found.")

		children = group_data.children if children_override is None else children_override
		if children:
			sc = sorted(children)
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
				group_intact = group_intact or cg_intact
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

		# if not group_intact and group is not self._top_group:
		# 	# This group is dangling, delete it.
		# 	if chains:
		# 		raise RuntimeError(
		# 			"This should not have happened: Group was considered dangling "
		# 			"but delivered chains!"
		# 		)
		# 	self._delete_group(group)

		return chains, group_intact

	def _build_draw_list_segments(
		self,
		start_group: "PNFGroup",
	) -> t.Tuple[t.Optional[DrawListSegment], t.List[int]]:
		"""
		Completely rebuilds the draw list walking from the given group.
		Returns ### TODO ### and a list
		of indices the index buffer must contain at that point.
		"""
		lgd = self._group_data # Le nano-optimization
		chains = [
			[(lgd[g], g) for g in raw_chain]
			for raw_chain in self._visit(start_group)[0]
		]
		del lgd

		if not chains: # is in a pickle
			return None, []

		# Below converts the group chains into GL calls.
		# TODO: This can certainly be optimized further by reordering
		# groups that share a GroupChain smartly in order to minimize
		# state switch cost.
		# Unfortunately, I am too stupid to figure out how, so just have
		# whatever this is. Smushes together common states, which is good
		# enough for the most part.
		for chain in chains:
			chain.sort(key=lambda g: hash(g[0].state.part_set))

		# AT THIS POINT the chains can be flattened.
		first_segment: t.Optional[DrawListSegment] = None

		last_segment: t.Optional[DrawListSegment] = None
		draw_list = []
		indices = []
		cur_state = GLState.from_state_parts()
		# Vertex layout is dictated by vertex domain and a group's program.
		cur_vertex_layout = None
		cur_draw_mode = None

		cur_index_start = 0
		cur_index_run = 0
		cur_group_run = []

		for chain in chains:
			for group_data, group in chain:
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

						# Attach new DLS
						new_segment = DrawListSegment(draw_list, cur_index_start, cur_index_run)
						new_segment._provoking_groups = cur_group_run
						if last_segment is None:
							first_segment = new_segment
						else:
							last_segment._next = new_segment
							new_segment._prev = last_segment

						last_segment = new_segment
						draw_list = []
						cur_group_run = []
						cur_index_start += cur_index_run
						cur_index_run = 0

					# VAO switch is needed for the new state.
					if cur_vertex_layout != new_vertex_layout:
						def bind_vao(d=group_data.interfacer.domain, p=group_data.state.program):
							# Buffers store their data locally and need to be told to upload it.
							# Using a buffer that does direct glNamedBufferSubData calls noticeably
							# slows down the freeplay scene, where a lot of vertex updates are
							# made each frame.
							for att in d.attributes.values():
								att.ensure()
							d.bind_vao(p, self.name)

						draw_list.append(bind_vao)
						cur_vertex_layout = new_vertex_layout

					# Extend the draw list with the required state switch calls
					cur_draw_mode = new_draw_mode
					draw_list.extend(state_switches)

				cur_group_run.append(group)

				# Extend vertex indices
				indices.extend(group_data.interfacer.indices)
				cur_index_run += len(group_data.interfacer.indices)

		# Final draw call
		if cur_index_run > 0:
			def final_draw_elements(
				m = cur_draw_mode,
				c = cur_index_run,
				t = _INDEX_TYPE,
				s = cur_index_start*_INDEX_TYPE_SIZE,
			):
				gl.glDrawElements(m, c, t, s)
				gl.glBindVertexArray(0)
			draw_list.append(final_draw_elements)

			new_segment = DrawListSegment(draw_list, cur_index_start, cur_index_run)
			new_segment._provoking_groups = cur_group_run
			if last_segment is None:
				first_segment = new_segment
			else:
				last_segment._next = new_segment
				new_segment._prev = last_segment

		return first_segment, indices

		# insert parent groups up to the top
		# on hitting a known parent group, we can now identify the order
		# of whatever we inserted

		# # Find adjacent DrawListSegments by walking down from the hook group
		# left_group: t.Optional[GroupData] = None
		# right_group: t.Optional[GroupData] = None
		# # OPT make children a b-tree or something
		# x = sorted(self._group_data[hook_group].children)
		# new_idx = x.index(fresh_group)
		# if new_idx < len(x) - 1:
		# 	right_group = self._group_data[x[new_idx + 1]]
		# if new_idx > 0:
		# 	left_group = self._group_data[x[new_idx - 1]]

	def _identify_changed_clusters(self) -> t.Dict["PNFGroup", "ClusterInfo"]:
		"""
		Returns subtrees of the draw tree that have been affected by
		group changes, as given by `self._dirty_groups`.
		# TODO more specific explanation of returned stuff
		"""
		gd = self._group_data
		cluster_map: t.Dict["PNFGroup", "PNFGroup"] = {}
		# Maps each dirty group and its ancestors to a group key
		# in `modified_clusters`.
		modified_clusters: t.Dict["PNFGroup", "ClusterInfo"] = {}

		# Identify changed clusters:
		for dirty_group in self._dirty_groups:
			if dirty_group in cluster_map:
				# Group has already been passed and was properly assigned to a cluster. Skip.
				continue

			current_cluster_set = set()
			current_cluster_ops = 0

			_reason = "?"
			# Walk up and update the current cluster data until a suitable parent is found.
			group = dirty_group
			# while (
			# 	group not in cluster_map and
			# 	group is not self._top_group and
			# 	gd[parent].draw_list_segment is None
			# ):
			while True:
				if group in cluster_map:
					_reason = "Group known"
					break
				if group is self._top_group:
					_reason = "Group is top"
					break
				# NOTE: Maybe the "intactness" is needed here, i.e. not scheduled for deletion,
				# has children, or is drawable
				if (
					gd[group].draw_list_segment is not None and
					group not in self._dirty_groups
				):
					_reason = "Has clean DLS"
					break
				current_cluster_set.add(group)
				current_cluster_ops |= gd[group].pending_operation
				group = self._top_group if group.parent is None else group.parent

			# at this point, group is either the top group or has been unaffected by recent
			# group changes and a draw list segment associated with it.
			hook_group = group

			# print(
			# 	f"Walking up {dirty_group} resulted in operations {current_cluster_ops}"
			# 	f", hook {hook_group}"
			# )

			ci = None
			if hook_group in modified_clusters:
				ci = modified_clusters[hook_group]
			elif hook_group in cluster_map:
				ci = modified_clusters[cluster_map[hook_group]]

			if ci is None:
				# Brand new cluster info
				ci = ClusterInfo()
				ci.root = hook_group
				ci.groups = current_cluster_set
				ci.operations = current_cluster_ops
				ci.r = _reason
				modified_clusters[hook_group] = ci
			else:
				# The same parent group has different child strands
				# that have been updated. Merge the current cluster into
				# the existing cluster then.
				ci.groups.update(current_cluster_set)
				ci.operations |= current_cluster_ops

			for reg_group in current_cluster_set:
				cluster_map[reg_group] = hook_group

		return modified_clusters

	def _regenerate(self) -> None:
		modified_clusters = self._identify_changed_clusters()
		print("Clussy:", modified_clusters)

		if next(iter(modified_clusters.keys())) is self._top_group:
			# The entire draw tree is affected, probably just created.
			assert len(modified_clusters) == 1
			print("Completely rebuilding draw list.")
			dl_head, indices = self._build_draw_list_segments(self._top_group)
			self._draw_list = dl_head
			self.index_buffer.set_size_and_data_py(indices)
		else:
			# TEMP rebuild anyways
			dl_head, indices = self._build_draw_list_segments(self._top_group)
			self._draw_list = dl_head
			self.index_buffer.set_size_and_data_py(indices)

		# Clear segments cause im not doing partial updates of them yet :troll:
		def _asdfdfd(g):
			gd = self._group_data[g]
			gd.draw_list_segment = None
			if gd.children:
				for c in gd.children:
					_asdfdfd(c)
		_asdfdfd(self._top_group)

		# Paint group data with the segments
		# This should cause the first draw list segment to always bubble to the top
		for seg in linked_list_iter(dl_head):
			for group in seg._provoking_groups:
				cur_group = group
				while True:# while self._group_data[cur_group].draw_list_segment is None:
					self._group_data[cur_group].draw_list_segment = seg
					if cur_group is self._top_group:
						break
					cur_group = self._top_group if cur_group.parent is None else cur_group.parent

		# /// WORK STARTS HERE /// #

		# NOTE: The order of clusters is not given.
		# This shouldn't matter too much.
		for cluster in modified_clusters.values():
			# # TODO: Perform some optimized actions for common cases.
			# if cluster.operations == GROUP_OPERATION_DEL:
			# 	# Cluster's members are meant to be entirely deleted.
			# 	pass

			# cluster.root is either top_group or has a draw list segment
			chains, intact = self._visit(cluster.root)
			if not intact:
				continue

			# merge chains with the existing draw list segments here



	def _tmp_clear_dirty(self, group: "PNFGroup") -> None:
		"""
		HACK ugly temp method that walks the entire group tree and
		clears its members pending attributes
		"""
		gd = self._group_data[group]
		gd.pending_operation = 0
		if gd.children:
			for c in gd.children:
				self._tmp_clear_dirty(c)

	def _remove_dead_leaves(self, group: "PNFGroup") -> int:
		c = 0
		for child in tuple(self._group_data[group].children):
			c += self._remove_dead_leaves(child)

		if (
			group is not self._top_group and
			(not self._group_data[group].children) and (
				self._group_data[group].pending_operation == GROUP_OPERATION_DEL or
				self._group_data[group].interfacer is None
			)
		):
			p = self._top_group if group.parent is None else group.parent
			self._group_data[p].children.remove(group)
			self._group_data.pop(group)
			return c + 1

		return c

	def check_dirty(self) -> bool:
		"""
		Checks whether this draw list is dirty. If it is, regenerates
		it and returns `True`. Otherwise, returns `False`.
		This should be called before each draw attempt.
		"""
		x = perf_counter()
		if not self._dirty_groups:
			return False

		# Sanity check
		if self._top_group in self._dirty_groups:
			print("[!] Top group is dirty, this may not happen.")
		self._regenerate()
		_rmd = self._remove_dead_leaves(self._top_group)
		self._tmp_clear_dirty(self._top_group)
		# # Deletion is insanely unstable atm, some temporary code to warn here.
		# while True:
		# 	for g in self._dirty_groups:
		# 		if self._group_data[g].pending_operation == GROUP_OPERATION_DEL:
		# 			break
		# 	else:
		# 		break
		# 	print("[!] Unable to remove deletion pending nodes, expect failure soon")
		# 	break

		if _rmd > 0:
			print(f"Removed {_rmd} dead groups")

		self._dirty_groups.clear()

		# print(f"draw list readjusted in {perf_counter() - x} secs.")
		return True

	def draw(self) -> None:
		dls = self._draw_list
		while dls is not None:
			for f in dls.funcs:
				f()
			dls = dls._next

	def delete(self) -> None:
		"""
		Properly deletes the DrawList and frees up any OpenGL objects.
		"""
		self.index_buffer.delete()

		# probably makes cyclic reference breakup easier
		for gd in self._group_data.values():
			gd.children.clear()

		# ditto
		dls = self._draw_list
		pdls = None
		while dls is not None:
			dls._prev = None
			pdls = dls
			dls = dls._next
			pdls._next = None

		self._group_data = None

	def dump_group_tree(self, gi: t.Iterable["PNFGroup"] = None, indent: int = 4) -> str:
		r = []
		if gi is None:
			gi = [self._top_group]
		for g in gi:
			gd = self._group_data[g]
			dls = gd.draw_list_segment
			r.append(f"{' ' * indent}Group {g} [DLS {None if dls is None else dump_id(dls)}]\n")
			if gd.interfacer is not None:
				r.append(
					f"{' ' * indent} Interfacer {dump_id(gd.interfacer)}; "
					f"state hash {hash(gd.state.part_set):>20}\n"
				)
			if gd.children:
				r.append(self.dump_group_tree(self._group_data[g].children, indent + 2))

		return "".join(r)

	def dump_debug_info(self) -> str:
		r = ["  Group tree:\n"]
		r.append(self.dump_group_tree())
		r.append("  Generated group chains:\n")
		r.append("\n".join("    " + repr(x) for x in self._visit(self._top_group)[0]))
		r.append("\n")
		r.append(
			f"  Calls in draw list: "
			f"{sum(len(seg.funcs) for seg in linked_list_iter(self._draw_list))}\n"
		)
		r.append(f"  Draw list segments: {sum(1 for _ in linked_list_iter(self._draw_list))}\n")
		r.append("  Provoking groups of draw list segments:\n")
		r.append("\n".join(
			"    " + repr(seg._provoking_groups) for seg in linked_list_iter(self._draw_list)
		))
		r.append("\n")
		return "".join(r)


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
		Gets an existing or new draw list.
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
		# draw calls and extremely annoying logic to keep vertex data in order.
		# In this project, most drawables are indexed sprites anyways.
		return self.add_indexed(size, draw_mode, group, [*range(size)], states, *data)

	def add_indexed(
		self,
		size: int,
		draw_mode: int,
		group: "PNFGroup",
		indices: t.Sequence[int],
		states: t.Dict[t.Hashable, GLState],
		*data: t.Union[str, t.Tuple[str, t.Any]],
	) -> PNFBatchInterfacer:
		attr_names = [x[0] if isinstance(x, tuple) else x for x in data]

		domain = self._get_vertex_domain(attr_names)
		start = domain.allocate(size)
		interfacer = PNFBatchInterfacer(
			domain, start, size, draw_mode, indices, self, group
		)
		self._introduce_interfacer(interfacer, states)

		# Set initial data
		for x in data:
			if not isinstance(x, tuple):
				continue
			interfacer.set_data(RE_VERTEX_FORMAT.match(x[0])[1], x[1])

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

	def modify_group(
		self, draw_list: t.Hashable, group: "PNFGroup", new_state: t.Optional[GLState] = None
	) -> None:
		"""
		Informs the given draw list that the given group's rendering
		circumstances have changed.
		This may include a new state, but will definitely cause a
		reprocessing of the group's draw calls.
		The draw list must exist.
		"""
		self._draw_lists[draw_list].modify_group(group, new_state)

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
		r = [f"Interfacers created and alive: {len(self._interfacers)}"]
		r.append(f"\nDraw list info:")
		for dl_name, dl in self._draw_lists.items():
			r.append(f"\nDraw list {dl_name}:\n")
			r.append(dl.dump_debug_info())

		# r.append("\nVertex Domain info:")
		# for key, vtxd in self._vertex_domains.items():
		# 	r.append(f"\n{sorted(key)}\n")
		# 	for name, att in vtxd.attributes.items():
		# 		r.append(f"  {name}: {att}\n")
		# 		arr = att.get_data_elements(0, 16)
		# 		r.append(f"  First 16 elements: {arr[:]}\n    [{arr}]\n")

		return "".join(r)


_fake_batch = PNFBatch()
def get_default_batch():
	return _fake_batch
