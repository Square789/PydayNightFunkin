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
U = t.TypeVar("U")

class PlainLoaderFunc(t.Protocol[T, ResourceOptionsBound]):
	def __call__(self, path: str) -> T:
		...
	def __call__(self, path: str, options: ResourceOptionsBound) -> T:
		...

class ASMLoaderFunc(t.Protocol[T, ResourceOptionsBound]):
	def __call__(self, what) -> T:
		...


class AssetNotFoundError(KeyError):
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
		asset_type_name: str,
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

# YAGNI
# class AssetTypeRegistryEntry:
# 	def __init__(
# 		self,
# 		name: str,
# 		cache_key_maker,
# 		options_factory,
# 		options_validator,
# 		generated_loader,
# 	) -> None:
# 		self.name = name
# 		self.cache_key_maker = cache_key_maker
# 		self.options_factory = options_factory
# 		self.options_validator = options_validator
# 		self.generated_loader = generated_loader
# 		self.is_complex = cache_key_maker is not None


class _AssetSystemManager:
	"""
	# TODO
	"""

	def __init__(self) -> None:
		self.asset_system_stack: t.List[AssetSystem] = []

		# self.asset_type_registry: t.Dict[str, AssetTypeRegistryEntry] = {}
		self.asset_type_registry: t.Set[str] = set()

		self.asset_dir = Path.cwd() / "assets"
		self._cache: t.Dict[t.Hashable, t.Any] = {}
		self._pyobj_cache: t.Dict[t.Hashable, t.Any] = {}

		_tbsize = min(4096, get_max_texture_size())
		make_tex_bin = lambda: TextureBin(_tbsize, _tbsize)
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

	def _get_full_path(self, tail: t.Union[Path, str]) -> str:
		return str(self.asset_dir / tail)

	@t.overload
	def _process_asset(self, path: str, asset_type_name: str, options: None) -> t.Tuple[str, None]:
		pass

	@t.overload
	def _process_asset(
		self, path: str, asset_type_name: str, options: ResourceOptionsBound,
	) -> t.Tuple[str, ResourceOptionsBound]:
		pass

	def _process_asset(self, path, asset_type_name, options):
		for as_ in reversed(self.asset_system_stack):
			have, true_path, true_options = as_.has_asset(path, asset_type_name, options)
			if have:
				return true_path, (options if true_options is None else true_options)

		raise AssetNotFoundError(f"Could not determine an asset system for asset {path}")

	def load_pyobj(self, ident: t.Hashable) -> t.Any:
		if ident in self._pyobj_cache:
			return self._pyobj_cache[ident]

		for as_ in reversed(self.asset_system_stack):
			have, o = as_.has_pyobj(ident)
			if have:
				self._pyobj_cache[ident] = o
				return o

		raise AssetNotFoundError(f"Could not find pyobj {ident!r} in current asset system stack")

	def load_image(
		self, path: str, cache: bool = False, options: t.Optional[ImageResourceOptions] = None
	) -> "Texture":
			in_opt = ImageResourceOptions() if options is None else options
			cache_key = (path, "image", in_opt)
			if cache_key in self._cache:
				return self._cache[cache_key]

			true_path_tail, opt = self._process_asset(path, "image", in_opt)
			if not isinstance(opt, type(in_opt)):
				raise RuntimeError("Asset system delivered incompatible options for asset.")

			data = self.store_image(
				image.load(self._get_full_path(true_path_tail)),
				opt.atlas_hint,
			)[0].get_texture()

			if cache:
				self._cache[cache_key] = data

			return data

	def _check_and_make_asset_type_cache(self, name: str) -> t.Dict:
		if name in self.asset_type_registry:
			raise ValueError(f"Asset of name {name} already exists")
		self._cache[name] = {}
		return self._cache[name]

	def remove_asset_type(self, name: str) -> None:
		if name not in self.asset_type_registry:
			raise KeyError(f"Cannot remove unknown asset type {name}")
		self.asset_type_registry.pop(name)
		self._cache.pop(name)

	def register_optionless_asset_type(self, name: str, loader_function):
		cache_dict = self._check_and_make_asset_type_cache(name)

		def gen_optionless_loader(path: str, cache: bool = True):
			if path in cache_dict:
				return cache_dict[path]

			true_path_tail, _ = self._process_asset(path, name, None)
			data = loader_function(self._get_full_path(true_path_tail))
			if cache:
				cache_dict[path] = data
			return data

		self.asset_type_registry.add(name)
		return gen_optionless_loader

	def register_asset_type(
		self,
		name: str,
		loader_function: PlainLoaderFunc[T, ResourceOptionsBound],
		options_factory: t.Callable[[], ResourceOptionsBound],
		options_validator: t.Optional[t.Callable[[t.Any], t.Union[str, bool]]] = None,
	) -> ASMLoaderFunc[T, ResourceOptionsBound]:
		cache_dict = self._check_and_make_asset_type_cache(name)

		def gen_loader(
			path: str,
			options: t.Optional[ResourceOptionsBound] = None,
			cache: bool = True,
		) -> T:
			options = options_factory() if options is None else options
			cache_key = (path, options)
			if cache_key in cache_dict:
				return cache_dict[cache_key]

			true_path_tail, true_options = self._process_asset(path, name, options)
			if true_options is not options and options_validator is not None:
				ovres = options_validator(true_options)
				if ovres is not True:
					raise RuntimeError(
						f"Options validator for asset type {name} disagreed with options "
						f"returned by an asset system{': ' + ovres if ovres else ''}."
					)

			data = loader_function(self._get_full_path(true_path_tail), true_options)
			if cache:
				cache_dict[cache_key] = data
			return data

		self.asset_type_registry.add(name)
		return gen_loader

	def register_complex_asset_type(self, name, cache_key_maker, loader_func) -> t.Callable:
		cache_dict = self._check_and_make_asset_type_cache(name)

		def gen_complex_loader(*args, cache: bool = True, **kwargs):
			cache_key = cache_key_maker(*args, **kwargs)
			if cache_key in cache_dict:
				return cache_dict[cache_key]
			data = loader_func(*args, **kwargs)
			if cache:
				cache_dict[cache_key] = data
			return data

		self.asset_type_registry.add(name)
		return gen_complex_loader

	def invalidate_cache(self, entries: t.Optional[t.Iterable[str]] = None) -> None:
		"""
		Invalidates the asset system's cache.
		If an iterable of resources is specified, only those will
		be removed from the cache, otherwise the entire cache is
		cleared.
		"""
		self._pyobj_cache.clear()
		if entries:
			for e in entries:
				# print(f"POPPING {e} FROM CACHE")
				self._cache.pop(e, None) # don't error on nonexistent cache entries
		else:
			# print("PURGING CACHE")
			self._cache.clear()


_asm = _AssetSystemManager()

def _load_bytes_plain(path: str) -> bytes:
	with open(path, "rb") as f:
		return f.read()
load_bytes = _asm.register_optionless_asset_type("bytes", _load_bytes_plain)

def _load_text_plain(path: str, options: TextResourceOptions) -> str:
	with open(path, "r", encoding=options.encoding) as f:
		return f.read()
load_text = _asm.register_asset_type("text", _load_text_plain, TextResourceOptions)

load_image = _asm.load_image

def _load_sound_plain(path: str, options: SoundResourceOptions) -> media.Source:
	return media.load(path, streaming=options.stream, decoder=options.decoder)
load_sound = _asm.register_asset_type("sound", _load_sound_plain, SoundResourceOptions)

def _load_xml_plain(path: str) -> ElementTree:
	et = ElementTree()
	# NOTE: The xml files contain the encoding inside them, which is mega stupid
	# since you need the encoding to properly parse them, so like ????
	# Unless there is some spec that declares that the first line MUST be valid ASCII
	# and then you have to change the encoding or whatever but i'm not gonna care about
	# all that and just have this work for utf8.
	with open(path, "r", encoding="utf-8") as f:
		et.parse(f, AlmostXMLParser())
	return et
load_xml = _asm.register_optionless_asset_type("xml", _load_xml_plain)

def _load_json_plain(path: str, options: JsonResourceOptions) -> t.Dict:
	with open(path, "r", encoding=options.encoding) as f:
		return json.load(f)
load_json = _asm.register_asset_type("json", _load_json_plain, JsonResourceOptions)

def _load_font_plain(path: str) -> None:
	font.add_file(path)
	return None
load_font = _asm.register_optionless_asset_type("font", _load_font_plain)


load_pyobj = _asm.load_pyobj
add_asset_system = _asm.add_asset_system
remove_asset_system = _asm.remove_asset_system
invalidate_cache = _asm.invalidate_cache
register_asset_type = _asm.register_asset_type
register_optionless_asset_type = _asm.register_optionless_asset_type
register_complex_asset_type = _asm.register_complex_asset_type
