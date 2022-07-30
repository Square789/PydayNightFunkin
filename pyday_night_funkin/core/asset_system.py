"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from collections import defaultdict
import json
import os
from pathlib import Path
import typing as t
from xml.etree.ElementTree import ElementTree

from loguru import logger
from pyglet import font
from pyglet import image
from pyglet.image import get_max_texture_size
from pyglet.image.atlas import AllocatorException, TextureBin
from pyglet import media

from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser
from pyday_night_funkin.core import ogg_decoder

if t.TYPE_CHECKING:
	from pyglet.image import AbstractImage, Texture
	from pyglet.media.codecs import MediaDecoder

ResourceOptionsBound = t.TypeVar("ResourceOptionsBound", bound="ResourceOptions")
T = t.TypeVar("T")


class AssetNotFoundError(ValueError):
	pass


class ResourceOptions:
	pass


class DummyResourceOptions:
	def __eq__(self, o: object) -> bool:
		return True if isinstance(o, DummyResourceOptions) else NotImplemented

	def __hash__(self) -> int:
		return hash(28576569317483667)


class ImageResourceOptions(ResourceOptions):
	def __init__(self, atlas_hint: t.Hashable = None) -> None:
		self.atlas_hint = atlas_hint

	def __eq__(self, o: object) -> bool:
		if isinstance(o, ImageResourceOptions):
			return self.atlas_hint == o.atlas_hint
		return NotImplemented

	def __hash__(self) -> int:
		return hash(self.atlas_hint)


class SoundResourceOptions(ResourceOptions):
	def __init__(self, stream: bool = False, decoder: t.Optional["MediaDecoder"] = None) -> None:
		if decoder is None:
			decoder = ogg_decoder.get_decoders()[0]
		self.stream = stream
		self.decoder = decoder

	def __eq__(self, o: object) -> bool:
		if isinstance(o, SoundResourceOptions):
			return self.stream == o.stream and self.decoder is o.decoder
		return NotImplemented

	def __hash__(self) -> int:
		return hash((self.stream, self.decoder))


class TextResourceOptions(ResourceOptions):
	def __init__(self, encoding: str = "utf-8") -> None:
		self.encoding = encoding

	def __eq__(self, o: object) -> bool:
		if isinstance(o, TextResourceOptions):
			return self.encoding == o.encoding
		return NotImplemented

	def __hash__(self) -> int:
		return hash(self.encoding)


class JsonResourceOptions(TextResourceOptions):
	pass


class AssetSystem:
	"""
	# TODO
	"""

	def __init__(
		self,
		asset_map: t.Dict[str, ResourceOptions],
		pyobj_map: t.Optional[t.Dict[t.Hashable, t.Any]] = None,
		allow_unknown: bool = True,
	) -> None:
		self._asset_map = asset_map
		self._pyobj_map = {} if pyobj_map is None else pyobj_map
		self._allow_unknown = allow_unknown

	def has_asset(
		self,
		path: str,
		options: ResourceOptionsBound,
	) -> t.Tuple[bool, t.Optional[str], t.Optional[ResourceOptionsBound]]:
		"""
		Determines whether an asset exists in this AssetSystem.
		The options can be given to hint at the asset type.
		If the asset exists, the tuple element at [1] will be the true
		path to it and [2] are the options the asset should be
		processed with.
		"""
		if path in self._asset_map:
			return (True, path, self._asset_map[path])

		if self._allow_unknown:
			return (True, path, options)
		else:
			return (False, None, None)

	def has_pyobj(self, ident: t.Hashable) -> t.Tuple[bool, t.Any]:
		if ident in self._pyobj_map:
			return (True, self._pyobj_map[ident])
		else:
			return (False, None)


class _AssetSystemManager():
	"""
	Singleton class for holding the active asset systems.
	# TODO
	"""

	def __init__(self) -> None:
		self.asset_system_stack: t.List[AssetSystem] = []

		self.asset_dir = Path.cwd() / "assets"
		self._cache: t.Dict[str, t.Any] = {}

		_tbsize = min(4096, get_max_texture_size())
		def make_tex_bin():
			return TextureBin(_tbsize, _tbsize)
		self._hinted_tex_bin: t.Dict[t.Hashable, TextureBin] = defaultdict(make_tex_bin)
		self._tex_bin = make_tex_bin()

	def add_asset_system(self, asset_system: AssetSystem) -> None:
		"""
		Adds an asset system to the asset system stack, which may
		influence the asset loading behavior.
		Invalidates the asset system manager's cache.
		"""
		self.asset_system_stack.append(asset_system)
		self.invalidate_cache()

	def remove_asset_system(self, asset_system: AssetSystem) -> None:
		"""
		Removes an asset system and invalidates the cache.
		"""
		try:
			self.asset_system_stack.remove(asset_system)
		except ValueError:
			return
		self.invalidate_cache()

	def store_image(
		self,
		img: "AbstractImage",
		atlas_hint: t.Optional[t.Hashable],
	) -> t.Tuple["AbstractImage", bool]:
		"""
		Stores an image in a TextureBin for merging and potential
		drawing speedup.
		Returns the image and whether it was successfully stored in an
		atlas.
		"""
		target_bin = (
			self._tex_bin if atlas_hint is None else
			self._hinted_tex_bin[atlas_hint]
		)
		try:
			return (target_bin.add(img), True)
		except AllocatorException as e:
			logger.warning(f"Failed storing image {img} in atlas {atlas_hint}: {e}")
			# NOTE: idk how OpenGL handles textures it can't fit into an
			# atlas, probably horribly slowly but whatever
			return (img, False)

	def _get_full_path(self, tail: os.PathLike) -> str:
		return str(self.asset_dir / tail)

	def _process_asset(
		self,
		path: str,
		options: ResourceOptionsBound,
	) -> t.Tuple[str, ResourceOptionsBound]:
		for i in range(len(self.asset_system_stack) - 1, -1, -1):
			have, true_path, true_options = self.asset_system_stack[i].has_asset(path, options)
			if have:
				return true_path, (options if true_options is None else true_options)

		raise AssetNotFoundError(f"Could not determine an asset system for asset {path}")

	def load_pyobj(self, ident: t.Hashable) -> t.Any:
		for i in range(len(self.asset_system_stack) - 1, -1, -1):
			have, o = self.asset_system_stack[i].has_pyobj(ident)
			if have:
				return o

		raise AssetNotFoundError(f"Could not find pyobj {ident!r} in current asset system stack")


	def loaderify(
		self,
		ro_factory: t.Callable[[], ResourceOptionsBound] = DummyResourceOptions,
	) -> t.Callable[
		[t.Callable[[str, ResourceOptionsBound], T]],
		t.Callable[[str, bool, t.Optional[ResourceOptionsBound]], T]
	]:
		def loaderify_decorator(
			orig_func: t.Callable[[str, ResourceOptionsBound], T]
		) -> t.Callable[[str, bool, t.Optional[ResourceOptionsBound]], T]:
			def loaderified(
				path: str,
				cache: bool = True,
				override_opt: t.Optional[ResourceOptionsBound] = None,
			) -> T:
				in_opt = ro_factory() if override_opt is None else override_opt
				cache_key = (path, in_opt)
				if cache_key in self._cache:
					return self._cache[cache_key]

				true_path, opt = self._process_asset(path, in_opt)
				data = orig_func(self._get_full_path(true_path), opt)

				if cache:
					self._cache[path] = data

				return data

			return loaderified
		return loaderify_decorator

	def loaderify_asm_access(
		self,
		ro_factory: t.Callable[[], ResourceOptionsBound] = DummyResourceOptions,
	) -> t.Callable[
		[t.Callable[["_AssetSystemManager", str, ResourceOptionsBound], T]],
		t.Callable[[str, bool, t.Optional[ResourceOptionsBound]], T]
	]:
		def loaderify_decorator(
			orig_func: t.Callable[["_AssetSystemManager", str, ResourceOptionsBound], T]
		) -> t.Callable[[str, bool, t.Optional[ResourceOptionsBound]], T]:
			def loaderified(
				path: str,
				cache: bool = True,
				override_opt: t.Optional[ResourceOptionsBound] = None,
			) -> T:
				in_opt = ro_factory() if override_opt is None else override_opt
				cache_key = (path, in_opt)
				if cache_key in self._cache:
					return self._cache[cache_key]

				true_path, opt = self._process_asset(path, in_opt)
				data = orig_func(self, self._get_full_path(true_path), opt)

				if cache:
					self._cache[cache_key] = data

				return data

			return loaderified
		return loaderify_decorator

	def invalidate_cache(self, entries: t.Optional[t.Iterable[str]] = None) -> None:
		"""
		Invalidates the asset system's cache.
		If an iterable of resources is specified, only those will
		be removed from the cache, otherwise the entire cache is
		cleared.
		"""
		if entries:
			for e in entries:
				# print(f"POPPING {e} FROM CACHE")
				self._cache.pop(e, None) # don't error on nonexistent cache entries
		else:
			# print("PURGING CACHE")
			self._cache.clear()


_asm = _AssetSystemManager()

@_asm.loaderify()
def load_bytes(path: str, _options) -> str:
	with open(path, "rb") as f:
		return f.read()

@_asm.loaderify(TextResourceOptions)
def load_text(path: str, options: TextResourceOptions) -> str:
	with open(path, "r", encoding=options.encoding) as f:
		return f.read()

@_asm.loaderify_asm_access(ImageResourceOptions)
def load_image(asm: _AssetSystemManager, path: str, options: ImageResourceOptions) -> "Texture":
	return asm.store_image(image.load(path), options.atlas_hint)[0].get_texture()

@_asm.loaderify(SoundResourceOptions)
def load_sound(path: str, options: SoundResourceOptions) -> media.Source:
	return media.load(path, streaming=options.stream, decoder=options.decoder)

@_asm.loaderify()
def load_xml(path: str, _options) -> ElementTree:
	et = ElementTree()
	# NOTE: The xml files contain the encoding inside them, which is mega stupid
	# since you need the encoding to properly parse them, so like ????
	# Unless there is some spec that declares that the first line MUST be valid ASCII
	# and then you have to change the encoding or whatever but i'm not gonna care about
	# all that and just have this work for utf8.
	with open(path, "r", encoding="utf-8") as f:
		et.parse(f, AlmostXMLParser())
	return et

@_asm.loaderify(JsonResourceOptions)
def load_json(path: str, options: JsonResourceOptions) -> t.Dict:
	with open(path, "r", encoding=options.encoding) as f:
		return json.load(f)

@_asm.loaderify()
def load_font(path: str, _options) -> None:
	font.add_file(path)
	return None

	
load_pyobj = _asm.load_pyobj
add_asset_system = _asm.add_asset_system
remove_asset_system = _asm.remove_asset_system
invalidate_cache = _asm.invalidate_cache
loaderify = _asm.loaderify
loaderify_asm_access = _asm.loaderify_asm_access
