
from collections import defaultdict
import typing as t


T = t.TypeVar("T")


class Registry(t.Generic[T]):
	"""
	Stupidly overengineered dict that not only stores things and their
	values but also "sources" these things came from.
	"""

	def __init__(self) -> None:
		self._dict = {}
		self._sources = defaultdict(set)

	def add(self, source_name: t.Hashable, name: t.Hashable, item: T) -> None:
		"""
		Adds something under the name `name` to this registry, stemming
		from source `source_name`.
		Raises a `ValueError` if `name` is already known.
		"""
		if name is None:
			raise TypeError("Registry names may not be `None`!")
		if name in self._dict:
			raise ValueError(f"{name} already exists in this registry!")

		self._dict[name] = item
		self._sources[source_name].add(name)

	def remove(self, name: t.Hashable) -> None:
		"""
		Removes the entry `name` from this registry.
		If no such entry exists, raises a `KeyError`.
		"""
		if name not in self._dict:
			raise KeyError(f"No such entry in registry: {name!r}")

		self._dict.pop(name)

	def purge_source(self, source_name: t.Hashable) -> None:
		"""
		Removes all entries stemming from the given source `source_name`.
		If no such source exists, raises a `KeyError`.
		"""
		if source_name not in self._sources:
			raise KeyError(f"Source {source_name!r} never introduced to this registry!")

		for name in self._sources.pop(source_name):
			self.remove(name)

	def get(self, name: t.Hashable) -> T:
		"""
		Retrieves an entry from the registry.
		"""
		return self._dict[name]

	def __getitem__(self, k: t.Hashable) -> T:
		return self.get(k)
