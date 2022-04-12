
import typing as t

T = t.TypeVar("T")


# NOTE: Expanding on this may be usable for partial draw list updates
# (in case i feel the need to torture myself some more).
# Rebuilding the entire thing when i. e. only a single note appears is silly


class LinkedList(t.Generic[T]):
	def __init__(self) -> None:
		self._head: t.Optional["LinkedListNode"] = None
		self._tail: t.Optional["LinkedListNode"] = None

	def __iter__(self) -> t.Iterable[T]:
		c = self._head
		while c is not None:
			yield c.value
			c = c.next

class LinkedListNode(t.Generic[T]):
	__slots__ = ("value", "next")

	def __init__(self, value: T, next: t.Optional["LinkedListNode"]) -> None:
		self.value = value
		self.next = next

