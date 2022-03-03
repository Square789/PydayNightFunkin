
import typing as t

T = t.TypeVar("T")


# NOTE: maybe using this for partial draw list updates.
# Rebuilding the entire thing when i. e. only a single note appears is silly

class LinkedListNode(t.Generic[T]):
	def __init__(self, value: T, next: t.Optional["LinkedListNode"]) -> None:
		self.value = value
		self.next = next

