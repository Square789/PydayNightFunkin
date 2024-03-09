"""
Rectangle allocator and deallocator.

This algorithm is entirely stolen from:
https://github.com/nical/guillotiere

It contains structures that are aggressively optimized to prevent
vector grow allocations, as well as linked-list references by index
instead of object, which probably does more harm than good when
translated to Python like this.
Couldn't be bothered to look into it for now.
"""

import enum
import typing as t


AllocIndex = t.Optional[int]


# The og implementation is sort of hardcoded to three of these, so i'm gonna
# hardcode even harder
RectCategory = t.NewType("RectCategory", int)
RECT_CATEGORY_SMALL = RectCategory(0)
RECT_CATEGORY_NORMAL = RectCategory(1)
RECT_CATEGORY_LARGE = RectCategory(2)
RECT_CATEGORY_COUNT = 3

# Probably slower than having C copy around a few entries using regular `pop` lol
def _swap_pop(l: t.List, i: int) -> None:
	if i < 0:
		raise ValueError("bre")
	if i >= len(l):
		raise ValueError("bre 2")
	if i != len(l) - 1:
		l[i] = l[-1]
	l.pop()


# TODO: These are only modified in one place.
# Might want to calculate width/height in __init__
class _PointRect:
	"""
	Crap rect class defining its rect by two points.
	Used by this module to freeload the guillotine allocator algorithm.
	"""

	__slots__ = ("min_x", "min_y", "max_x", "max_y")

	def __init__(self, min_x: int, min_y: int, max_x: int, max_y: int) -> None:
		self.min_x = min_x
		self.min_y = min_y
		self.max_x = max_x
		self.max_y = max_y

	def is_empty(self):
		return self.min_x == self.max_x or self.min_y == self.max_y

	def width(self) -> int:
		return self.max_x - self.min_x

	def height(self) -> int:
		return self.max_y - self.min_y

	def area(self) -> int:
		return self.width() * self.height()

	def size(self) -> t.Tuple[int, int]:
		return (self.width(), self.height())

	def copy(self) -> "_PointRect":
		return _PointRect(self.min_x, self.min_y, self.max_x, self.max_y)

	def __repr__(self) -> str:
		return f"PointRect({self.min_x}, {self.min_y}, {self.max_x}, {self.max_y})"

	def __eq__(self, o: object) -> bool:
		if not isinstance(o, _PointRect):
			return NotImplemented
		return (
			self.min_x == o.min_x and
			self.min_y == o.min_y and
			self.max_x == o.max_x and
			self.max_y == o.max_y
		)


class Allocation:
	__slots__ = ("id", "x", "y")

	def __init__(self, id_: int, rect: _PointRect) -> None:
		self.id = id_
		self.x = rect.min_x
		self.y = rect.min_y

	def __repr__(self) -> str:
		return f"Allocation({self.id}, ({self.x}, {self.y}))"


class NodeKind(enum.IntEnum):
	FREE = 0
	ALLOC = 1
	CONTAINER = 2
	UNUSED = 3


class _Node:
	__slots__ = ("parent", "next", "prev", "rect", "kind", "vertical")

	def __init__(
		self,
		rect: _PointRect,
		kind: NodeKind,
		vertical: bool,
		parent: AllocIndex = None,
		next: AllocIndex = None,
		prev: AllocIndex = None,
	) -> None:
		self.parent: AllocIndex = parent
		self.next: AllocIndex = next
		self.prev: AllocIndex = prev
		self.rect = rect
		self.kind = kind
		self.vertical = vertical


def guillotine_rect(
	to_split: _PointRect, req_w: int, req_h: int, is_vertical: bool
) -> t.Tuple[_PointRect, _PointRect, bool]:
	leftover_candidate_to_right = _PointRect(
		to_split.min_x + req_w, to_split.min_y,
		to_split.max_x,         to_split.min_y + req_h
	)
	leftover_candidate_to_bottom = _PointRect(
		to_split.min_x,         to_split.min_y + req_h,
		to_split.min_x + req_w, to_split.max_y
	)

	if (req_w, req_h) == to_split.size():
		return (_PointRect(0, 0, 0, 0), _PointRect(0, 0, 0, 0), is_vertical)

	elif leftover_candidate_to_right.area() > leftover_candidate_to_bottom.area():
		return (
			_PointRect(
				leftover_candidate_to_right.min_x, leftover_candidate_to_right.min_y,
				leftover_candidate_to_right.max_x, to_split.max_y
			),
			leftover_candidate_to_bottom,
			False,
		)

	else:
		return (
			_PointRect(
				leftover_candidate_to_bottom.min_x, leftover_candidate_to_bottom.min_y,
				to_split.max_x,                     leftover_candidate_to_bottom.max_y
			),
			leftover_candidate_to_right,
			True,
		)


class GuillotineAllocator:
	def __init__(
		self,
		width: int,
		height: int,
		small_limit: int = 32,
		large_limit: int = 512,
	) -> None:
		self._width = width
		self._height = height

		self._small_limit = small_limit
		self._large_limit = large_limit

		self._nodes: t.List[_Node] = [_Node(_PointRect(0, 0, width, height), NodeKind.FREE, True)]
		self._root_node: AllocIndex = 0

		self._free_lists: t.List[t.List[AllocIndex]] = [[] for _ in range(RECT_CATEGORY_COUNT)]
		self._free_lists[self._find_classifiction(width, height)].append(0)

		self._unused_nodes: AllocIndex = None

	def _find_classifiction(self, width: int, height: int) -> RectCategory:
		if width >= self._large_limit or height >= self._large_limit:
			return RECT_CATEGORY_LARGE
		if width >= self._small_limit or height >= self._small_limit:
			return RECT_CATEGORY_NORMAL
		return RECT_CATEGORY_SMALL

	def _find_rect(self, width: int, height: int) -> AllocIndex:
		ideal_category = self._find_classifiction(width, height)
		use_worst_fit = ideal_category == RECT_CATEGORY_LARGE

		for category in range(ideal_category, RECT_CATEGORY_COUNT):
			candidate_score = 0 if use_worst_fit else 0xFFFFFFFF
			candidate = None

			free_list_idx = 0
			while free_list_idx < len(self._free_lists[category]):
				id_ = self._free_lists[category][free_list_idx]
				assert id_ is not None

				node = self._nodes[id_]
				if node.kind is not NodeKind.FREE:
					_swap_pop(self._free_lists[category], free_list_idx)
					# self._free_lists[category].pop(free_list_idx)
					continue

				dx = node.rect.width() - width
				dy = node.rect.height() - height

				if dx >= 0 and dy >= 0:
					if dx == 0 or dy == 0:
						candidate = (id_, free_list_idx)
						break

					score = min(dx, dy)
					if (
						(use_worst_fit and score > candidate_score) or
						(not use_worst_fit and score < candidate_score)
					):
						candidate_score = score
						candidate = (id_, free_list_idx)

				free_list_idx += 1

			if candidate is not None:
				_swap_pop(self._free_lists[category], candidate[1])
				# self._free_lists[category].pop(candidate[1])
				return candidate[0]

		return None

	def _get_new_node(self) -> int:
		idx = self._unused_nodes
		if idx is not None:
			self._unused_nodes = self._nodes[idx].next
			assert self._nodes[idx].kind is NodeKind.UNUSED
			return idx

		self._nodes.append(_Node(_PointRect(0, 0, 0, 0), NodeKind.UNUSED, False))
		return len(self._nodes) - 1

	def _mark_node_unused(self, id_: AllocIndex) -> None:
		assert id_ is not None
		assert self._nodes[id_].kind is not NodeKind.UNUSED

		self._nodes[id_].kind = NodeKind.UNUSED
		self._nodes[id_].next = self._unused_nodes
		self._unused_nodes = id_

	def _add_free_rect(self, free_id: AllocIndex, rect_size: t.Tuple[int, int]) -> None:
		assert free_id is not None
		assert self._nodes[free_id].kind is NodeKind.FREE

		self._free_lists[self._find_classifiction(*rect_size)].append(free_id)
		# print(f"{free_id} now points to free rect {self._nodes[free_id].rect}")

	def _merge_siblings(self, a: int, b: int, vertical: bool) -> None:
		assert self._nodes[a].kind is NodeKind.FREE and self._nodes[b].kind is NodeKind.FREE
		# print(f"merging {b} into {a}. {vertical=}")

		r1 = self._nodes[a].rect
		r2 = self._nodes[b].rect

		merge_size = r2.size()
		if vertical:
			assert r1.min_x == r2.min_x
			assert r1.max_x == r2.max_x
			self._nodes[a].rect.max_y += merge_size[1]
		else:
			assert r1.min_y == r2.min_y
			assert r1.max_y == r2.max_y
			self._nodes[a].rect.max_x += merge_size[0]

		nn = self._nodes[b].next
		self._nodes[a].next = nn
		if nn is not None:
			self._nodes[nn].prev = a

		self._mark_node_unused(b)

	def allocate(self, width: int, height: int):
		chosen_id = self._find_rect(width, height)
		if chosen_id is None:
			return None

		node_chosen = self._nodes[chosen_id]
		rect_chosen = node_chosen.rect.copy()
		allocated_rect = _PointRect(
			rect_chosen.min_x,         rect_chosen.min_y,
			rect_chosen.min_x + width, rect_chosen.min_y + height,
		)
		chosen_vertical = node_chosen.vertical

		assert node_chosen.kind is NodeKind.FREE

		split_rect, leftover_rect, vertical = guillotine_rect(
			node_chosen.rect, width, height, chosen_vertical
		)

		split_id: AllocIndex = None
		allocated_id: AllocIndex = None
		leftover_id: AllocIndex = None

		if vertical == chosen_vertical:
			if split_rect.is_empty():
				split_id = None
			else:
				split_id = self._get_new_node()
				n = self._nodes[split_id]
				n.rect = split_rect
				n.kind = NodeKind.FREE
				n.vertical = chosen_vertical
				n.parent = node_chosen.parent
				n.next = node_chosen.next
				n.prev = chosen_id

				nnext = node_chosen.next

				node_chosen.next = split_id
				if nnext is not None:
					self._nodes[nnext].prev = split_id

			if leftover_rect.is_empty():
				allocated_id = chosen_id
				leftover_id = None

				n = self._nodes[chosen_id]
				n.kind = NodeKind.ALLOC
				n.rect = allocated_rect
			else:
				self._nodes[chosen_id].kind = NodeKind.CONTAINER
				allocated_id = self._get_new_node()
				leftover_id = self._get_new_node()

				n = self._nodes[allocated_id]
				n.rect = allocated_rect
				n.kind = NodeKind.ALLOC
				n.vertical = not chosen_vertical
				n.parent = chosen_id
				n.next = leftover_id
				n.prev = None

				n = self._nodes[leftover_id]
				n.rect = leftover_rect
				n.kind = NodeKind.FREE
				n.vertical = not chosen_vertical
				n.parent = chosen_id
				n.next = None
				n.prev = allocated_id
		else:
			self._nodes[chosen_id].kind = NodeKind.CONTAINER

			if split_rect.is_empty():
				split_id = None
			else:
				split_id = self._get_new_node()
				n = self._nodes[split_id]
				n.rect = split_rect
				n.kind = NodeKind.FREE
				n.vertical = not chosen_vertical
				n.parent = chosen_id
				n.next = None
				n.prev = None

			if leftover_rect.is_empty():
				allocated_id = self._get_new_node()
				leftover_id = None

				n = self._nodes[allocated_id]
				n.rect = allocated_rect
				n.kind = NodeKind.ALLOC
				n.vertical = not chosen_vertical
				n.parent = chosen_id
				n.next = split_id
				n.prev = None

				self._nodes[split_id].prev = allocated_id
			else:
				container_id = self._get_new_node()
				n = self._nodes[container_id]
				n.rect = _PointRect(0, 0, 0, 0)
				n.kind = NodeKind.CONTAINER
				n.vertical = not chosen_vertical
				n.parent = chosen_id
				n.next = split_id
				n.prev = None

				self._nodes[split_id].prev = container_id

				allocated_id = self._get_new_node()
				leftover_id = self._get_new_node()

				n = self._nodes[allocated_id]
				n.rect = allocated_rect
				n.kind = NodeKind.ALLOC
				n.vertical = chosen_vertical
				n.parent = container_id
				n.next = leftover_id
				n.prev = None

				n = self._nodes[leftover_id]
				n.rect = leftover_rect
				n.kind = NodeKind.FREE
				n.vertical = chosen_vertical
				n.parent = container_id
				n.next = None
				n.prev = allocated_id

		assert self._nodes[allocated_id].kind is NodeKind.ALLOC

		if split_id is not None:
			self._add_free_rect(split_id, split_rect.size())

		if leftover_id is not None:
			self._add_free_rect(leftover_id, leftover_rect.size())

		return Allocation(allocated_id, allocated_rect)

	def deallocate(self, allocation_id: int) -> None:
		if allocation_id >= len(self._nodes):
			raise ValueError(f"Unknown/Invalid allocation ID {allocation_id}")
		if self._nodes[allocation_id].kind is not NodeKind.ALLOC:
			raise ValueError("Invalid allocation ID {allocation_id}")

		self._nodes[allocation_id].kind = NodeKind.FREE
		# print("@", allocation_id, "is now free")

		while True:
			# print(f"deallocating {allocation_id}")
			is_vertical = self._nodes[allocation_id].vertical
			next_id = self._nodes[allocation_id].next
			prev_id = self._nodes[allocation_id].prev

			if next_id is not None and self._nodes[next_id].kind is NodeKind.FREE:
				self._merge_siblings(allocation_id, next_id, is_vertical)

			if prev_id is not None and self._nodes[prev_id].kind is NodeKind.FREE:
				self._merge_siblings(prev_id, allocation_id, is_vertical)
				allocation_id = prev_id

			parent = self._nodes[allocation_id].parent
			if (
				self._nodes[allocation_id].prev is None and
				self._nodes[allocation_id].next is None and
				parent is not None
			):
				# Are we an isolated child? If yes, mark selves as unused and attempt
				# to repeat merging with parent
				assert self._nodes[parent].kind is NodeKind.CONTAINER

				self._mark_node_unused(allocation_id)

				self._nodes[parent].rect = self._nodes[allocation_id].rect.copy()
				#print(f"{allocation_id} is isolated; marking as unused and jumping to {parent=}")
				self._nodes[parent].kind = NodeKind.FREE

				assert self._nodes[parent].rect == self._nodes[allocation_id].rect

				allocation_id = parent
			else:
				self._add_free_rect(allocation_id, self._nodes[allocation_id].rect.size())
				break

	def is_empty(self) -> bool:
		root = self._nodes[self._root_node]
		return root.kind is NodeKind.FREE and root.next is None


if __name__ == "__main__":
	def dump_svg(al: GuillotineAllocator, suffix = ""):
		import os
		from xml.etree import ElementTree

		t = ElementTree.ElementTree(ElementTree.Element(
			"svg",
			{
				"width": str(al._width),
				"height": str(al._height),
				"xmlns": "http://www.w3.org/2000/svg",
			},
		))
		for i, n in enumerate(al._nodes):
			if n.kind is NodeKind.UNUSED or n.kind is NodeKind.CONTAINER:
				continue
			t.getroot().append(ElementTree.Element(
				"rect",
				{
					"fill": "#abf" if n.kind is NodeKind.FREE else f"#a0{i % 256:02X}{i**2 % 256:02X}",
					"x": str(n.rect.min_x),
					"y": str(n.rect.min_y),
					"width": str(n.rect.width()),
					"height": str(n.rect.height()),
					"style": "stroke-width: 2; stroke: rgb(0, 0, 0);",
				}
			))
			text = ElementTree.Element(
				"text",
				{"x": str(n.rect.min_x + 2), "y": str(n.rect.min_y + 16)}
			)
			text.text = str(i)
			t.getroot().append(text)

		with open(os.path.join(os.getcwd(), f"guillotine_allocator{suffix}.svg"), "wb") as f:
			f.write(b"<?xml version=\"1.0\" ?>\n")
			t.write(f, "utf-8")

		# print(f"==> Written guillotine_allocator{suffix}.svg")

	allocator = GuillotineAllocator(1000, 1000, 16, 256)

	dump_svg(allocator)

	print("=v= Test A")
	full_allocation = allocator.allocate(1000, 1000)
	print("=v= Test A ok")
	print("=v= Test B")
	assert allocator.allocate(1, 1) is None
	print("=v= Test B ok")

	print("=v= Test C")
	allocator.deallocate(full_allocation.id)
	print("=v= Test C ok")

	print("=v= Test QA: (100, 1000)")
	a = allocator.allocate(100, 1000); print(a)
	dump_svg(allocator, "AA")
	print("=v= Test QA ok")
	print("=v= Test QB: (900, 200)")
	b = allocator.allocate(900, 200); print(b)
	dump_svg(allocator, "AB")
	print("=v= Test QB ok")
	print("=v= Test QC: (300, 200)")
	c = allocator.allocate(300, 200); print(c)
	dump_svg(allocator, "AC")
	print("=v= Test QC ok")
	print("=v= Test QD: (200, 300)")
	d = allocator.allocate(200, 300); print(d)
	dump_svg(allocator, "AD")
	print("=v= Test QD ok")
	print("=v= Test QE: (100, 300)")
	e = allocator.allocate(100, 300); print(e)
	dump_svg(allocator, "AE")
	print("=v= Test QE ok")
	print("=v= Test QF: (100, 300)")
	f = allocator.allocate(100, 300); print(f)
	dump_svg(allocator, "AF")
	print("=v= Test QF ok")
	print("=v= Test QG: (100, 300)")
	g = allocator.allocate(100, 300); print(g)
	dump_svg(allocator, "AG")
	print("=v= Test QG ok")

	print("=v= Test Deallocation b")
	allocator.deallocate(b.id)
	dump_svg(allocator, "AH")
	print("=v= Test Deallocation b ok")
	print("=v= Test Deallocation f")
	allocator.deallocate(f.id)
	dump_svg(allocator, "AI")
	print("=v= Test Deallocation f ok")
	print("=v= Test Deallocation c")
	allocator.deallocate(c.id)
	dump_svg(allocator, "AJ")
	print("=v= Test Deallocation c ok")
	print("=v= Test Deallocation e")
	allocator.deallocate(e.id)
	dump_svg(allocator, "AK")
	print("=v= Test Deallocation e ok")
	print("=v= Test QH")
	h = allocator.allocate(500, 200); print(h)
	dump_svg(allocator, "AL")
	print("=v= Test QH ok")
	print("=v= Test Deallocation a")
	allocator.deallocate(a.id)
	dump_svg(allocator, "AM")
	print("=v= Test Deallocation a ok")
	print("=v= Test QL")
	i = allocator.allocate(500, 200); print(i)
	dump_svg(allocator, "AN")
	print("=v= Test QL ok")
	print("=v= Test Deallocation g")
	allocator.deallocate(g.id)
	dump_svg(allocator, "AO")
	print("=v= Test Deallocation g ok")
	print("=v= Test Deallocation h")
	allocator.deallocate(h.id)
	dump_svg(allocator, "AP")
	print("=v= Test Deallocation h ok")
	print("=v= Test Deallocation d")
	allocator.deallocate(d.id)
	dump_svg(allocator, "AQ")
	print("=v= Test Deallocation d ok")
	print("=v= Test Deallocation i")
	allocator.deallocate(i.id)
	dump_svg(allocator, "AR")
	print("=v= Test Deallocation i ok")

	full_again = allocator.allocate(1000, 1000)
	assert allocator.allocate(1, 1) is None
	allocator.deallocate(full_again.id)
