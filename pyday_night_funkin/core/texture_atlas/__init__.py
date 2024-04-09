
import typing as t

from pyglet.image import ImageData, Texture, TextureRegion

from .allocator import GuillotineAllocator


class TextureAtlas:
	def __init__(self, tex_width: int, tex_height: int) -> None:
		self._texture = Texture.create(tex_width, tex_height, blank_data=False)
		self._allocator = GuillotineAllocator(tex_width, tex_height)

	def add(self, image_data: ImageData) -> t.Optional[t.Tuple[TextureRegion, int]]:
		w, h = image_data.width, image_data.height

		allocation = self._allocator.allocate(w, h)
		if allocation is None:
			return None

		self._texture.blit_into(image_data, allocation.x, allocation.y, 0)
		return (self._texture.get_region(allocation.x, allocation.y, w, h), allocation.id)

	def remove(self, allocation_id: int) -> None:
		self._allocator.deallocate(allocation_id)

	def delete(self) -> None:
		self._texture.delete()

		del self._texture
		del self._allocator


class TextureBinAllocationIdentifier:
	__slots__ = ("atlas_idx", "atlas_allocation_id")

	def __init__(self, atlas_idx: int, atlas_allocation_id: int) -> None:
		self.atlas_idx = atlas_idx
		self.atlas_allocation_id = atlas_allocation_id


class TextureBin:
	"""
	Manages multiple atlases.
	"""

	def __init__(self, atlas_width: int, atlas_height: int) -> None:
		self._free_atlas_list_indices = []
		self._atlases: t.List[t.Optional[TextureAtlas]] = []
		self._atlas_width = atlas_width
		self._atlas_height = atlas_height

	def can_hold(self, image_data: ImageData) -> bool:
		return image_data.width <= self._atlas_width and image_data.height <= self._atlas_height

	def add(self, image_data: ImageData) -> t.Tuple[TextureRegion, TextureBinAllocationIdentifier]:
		for i, atlas in enumerate(self._atlases):
			if atlas is None:
				continue

			add_res = atlas.add(image_data)
			if add_res is None:
				continue

			atlas_idx = i

			break
		else:
			new_atlas = TextureAtlas(self._atlas_width, self._atlas_height)
			if self._free_atlas_list_indices:
				atlas_idx = self._free_atlas_list_indices.pop()
				self._atlases[atlas_idx] = new_atlas
			else:
				atlas_idx = len(self._atlases)
				self._atlases.append(new_atlas)

			add_res = new_atlas.add(image_data)
			assert add_res is not None

		return add_res[0], TextureBinAllocationIdentifier(atlas_idx, add_res[1])

	def get_area(self) -> int:
		"""
		Returns the area all of this ``TextureBin``'s atlases occupy.
		"""
		r = 0
		for atlas in self._atlases:
			if atlas is not None:
				r += self._atlas_width * self._atlas_height
		return r

	def remove(self, identifier: TextureBinAllocationIdentifier) -> None:
		"""
		Marks a region previously allocated by this bin as free.
		Its data is not erased but may be overwritten again.
		It may also cause the using atlas to be deleted, so: Don't use
		the associated texture region anymore.
		"""
		atlas = self._atlases[identifier.atlas_idx]
		atlas.remove(identifier.atlas_allocation_id)
		if not atlas._allocator.is_empty():
			return

		# print("deleted texture atlas thank you very much")
		atlas.delete()
		self._atlases[identifier.atlas_idx] = None
		self._free_atlas_list_indices.append(identifier.atlas_idx)
