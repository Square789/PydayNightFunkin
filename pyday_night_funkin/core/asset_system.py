"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol


# NOTE: The typing in this module is severely lacking due to my brainworm
# to support 3.8, making ParamSpec impossible.
# Typing behavior is for now explicitly forced in for the base loaders.
# I tried, it wouldn't be possible anyways for now due to my desire to add
# the `cache` kwarg-parameter to loader functions.
# Will simply need to wait until stuff like the following make it through
# https://github.com/python/mypy/issues/16120
# https://discuss.python.org/t/unpacking-typedicts-for-specifying-more-complex-paramspecs/34234

import abc
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, Future
import enum
import fnmatch
import functools
import gc
import glob
import inspect
import json
from math import exp, tau, sqrt
import os
from pathlib import Path
import queue
import re
import sys
import threading
from time import perf_counter, sleep
import typing as t
from xml.etree.ElementTree import ElementTree

from loguru import logger
from pyglet import clock
from pyglet import image
from pyglet.image import AbstractImage, Texture
from pyglet.math import Vec2
from pyglet import media
from pyglet.media.codecs.base import Source, StaticSource

from pyday_night_funkin.core.animation import FrameCollection
from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser
from pyday_night_funkin.core import ogg_decoder
from pyday_night_funkin.core.texture_atlas import TextureBin

if t.TYPE_CHECKING:
	from pyglet.image import AbstractImage, ImageData, Texture
	from pyglet.media.codecs import MediaDecoder


T = t.TypeVar("T")
U = t.TypeVar("U")
# P = ParamSpec("P")
CacheT = t.TypeVar("CacheT", bound="Cache")
BaseAssetProviderT = t.TypeVar("BaseAssetProviderT", bound="BaseAssetProvider")

PostLoadProcessor = t.Callable[[T], T]
ParameterTuple = t.Tuple[t.Tuple[t.Any, ...], t.Dict[str, t.Any]]
AssetIdentifier = t.Tuple[str, t.Hashable]


_BUILTIN_EXTENSION_MAP = {
	"txt": "text",
	"bin": "bytes",
	"xml": "xml",
	"json": "json",
	"ogg": "sound",
	"png": "image",
	"jpg": "image",
	"jpeg": "image",
	"gif": "image",
	"bmp": "image",
}


def path_to_string(path: t.Union[str, Path]) -> str:
	"""
	Possibly stringifies a path.
	This method is used internally to ensure regular asset routers
	as well as their `has_asset` method always receive strings.
	"""
	return path if isinstance(path, str) else str(path)


_SQRT_TAU = sqrt(tau)
def ndist_1(x: float, sigma: float) -> float:
	"""
	Normal distribution with standard deviation hardcoded to 1
	(aka curve peaks at 1.0)
	"""
	return exp(-0.5 * ((x - 1.0)/sigma)**2.0) / (sigma * _SQRT_TAU)


class AssetNotFoundError(KeyError):
	pass


class AssetRouterEntry:
	__slots__ = ("path", "options", "post_load_processor", "terminal")

	def __init__(
		self,
		path: t.Optional[str] = None,
		options: t.Optional[t.Dict[str, t.Any]] = None,
		post_load_processor: t.Optional[PostLoadProcessor] = None,
		terminal: bool = True,
	) -> None:
		self.path = path
		self.options = options
		self.post_load_processor = post_load_processor
		self.terminal = terminal


class LibrarySpecPattern:
	def __init__(
		self,
		pattern: str,
		exclude: t.Tuple[str, ...] = (),
		type_: t.Optional[str] = None
	) -> None:
		self.pattern = pattern
		self.exclude = exclude
		self.asset_type_name = type_


class BaseAssetRouter:
	def __init__(self) -> None:
		pass

	def has_asset(
		self, path: str, asset_type_name: str, options: t.Dict[str, t.Any]
	) -> t.Optional[
		t.Tuple[bool, str, t.Optional[t.Dict[str, t.Any]], t.Optional[PostLoadProcessor]]
	]:
		"""
		Determines whether an asset exists in this AssetRouter by its
		path.
		If the asset exists, a four-length tuple is returned:
		- The first element will be a boolean determining whether this
		  hit was terminal. If it was, the returned path is assumed to
		  be absolute and the search is stopped.
		- The second element will be the path to the asset.
		  It must be absolute if the previous element was ``True``,
		  otherwise it must remain relative and may be the input path
		  unchanged.
		- The third element may be additional options the asset
		  should be loaded with in the form of a dict that the received
		  kwargs will be updated with.
		  If no such options are supposed to be used, return `None`.
		- The fourth may be a function that modifies the asset after
		  loading, or `None` if this is not required.

		If the asset does not exist for this asset router, it returns
		`None`.
		"""
		raise NotImplementedError()

	def has_complex_asset(
		self, asset_type_name: str, options: t.Dict[str, t.Any]
	) -> t.Optional[t.Tuple[bool, t.Optional[t.Dict[str, t.Any]], t.Optional[PostLoadProcessor]]]:
		raise NotImplementedError()

	def has_pyobj(self, ident: t.Hashable) -> t.Tuple[bool, t.Any]:
		"""
		Returns a two-element tuple indicating whether this asset
		system knows an object with this name.
		If it does, [0] is True and [1] will be the object.
		If it does not, [0] is False and [1] irrelevant.
		"""
		raise NotImplementedError()

	def discover_libraries(
		self,
		library_specs: t.Dict[str, t.Tuple[LibrarySpecPattern, ...]],
	) -> t.Dict[str, t.Dict[str, t.Sequence[ParameterTuple]]]:
		"""
		Possibly discover any of the given libraries.
		Given a tuple of specification patterns for each library, the
		AssetRouter may choose to modify them, scan the directories
		within and return a dict mapping each found library to a dict
		mapping asset types to (args, kwargs) 2-length tuples denoting
		the parameters the type's loader is to be called with.
		"""
		return {}

	def get_library_specs(self) -> t.Dict[str, t.Tuple[LibrarySpecPattern, ...]]:
		"""
		Get the library specification patterns exported by this
		AssetRouter.
		They are formed exclusively through AssetRouters, similar to
		pyobj loading.
		"""
		return {}


class _RouteInfo:
	__slots__ = ("paths", "regexes")

	def __init__(
		self,
		paths: t.Dict[str, AssetRouterEntry],
		regexes: t.Sequence[t.Tuple[re.Pattern, AssetRouterEntry]],
	) -> None:
		self.paths = paths
		self.regexes = regexes


class AssetRouter(BaseAssetRouter):
	"""
	An asset router with some convenience builtin.
	See ``__init__``. TODO: maybe actually write something in __init__ lol
	"""

	def __init__(
		self,
		asset_directory: t.Union[str, Path] = "",
		unconditional_asset_map: t.Optional[t.Dict[str, AssetRouterEntry]] = None,
		per_asset_type_asset_map: t.Optional[t.Dict[str, t.Dict[str, AssetRouterEntry]]] = None,
		pyobj_map: t.Optional[t.Dict[t.Hashable, t.Any]] = None,
		library_specs: t.Optional[t.Dict[str, t.Tuple[LibrarySpecPattern, ...]]] = None,
	) -> None:
		self._dir = path_to_string(asset_directory)

		self._pyobj_map = {} if pyobj_map is None else pyobj_map

		self._library_specs = {} if library_specs is None else library_specs

		_asset_maps: t.Dict[str, _RouteInfo] = {}
		if per_asset_type_asset_map is not None:
			for target_type_specifier, orig_router_map in per_asset_type_asset_map.items():
				ri = self._process_asset_map(orig_router_map)
				if ri.regexes or ri.paths:
					_asset_maps[target_type_specifier] = ri

		self._asset_maps = _asset_maps

		if unconditional_asset_map is not None:
			unc = self._process_asset_map(unconditional_asset_map)
			self._unc_asset_map = unc.paths
			self._unc_regexes = unc.regexes
		else:
			self._unc_asset_map = {}
			self._unc_regexes = []

	def _process_asset_map(self, router_map: t.Dict[str, AssetRouterEntry]) -> _RouteInfo:
		regexes: t.List[t.Tuple[re.Pattern, AssetRouterEntry]] = []
		r_router_map = {}
		for k, e in router_map.items():
			if k.startswith("//re:"):
				regexes.append((re.compile(k[5:]), e))
			elif k.startswith("//"):
				raise ValueError("Bad special path specifier. Must be '//re:'")
			else:
				r_router_map[k] = e

		return _RouteInfo(r_router_map, regexes)

	def _absolutize_path(self, path: str) -> str:
		return os.path.join(self._dir, path)

	def _process_asset_hit(self, path: str, entry: AssetRouterEntry):
		terminal = entry.terminal
		e_path = entry.path
		if e_path is None:
			f_path = self._absolutize_path(path) if terminal else path
		else:
			# TODO: Path modification in case of regex/globs?
			f_path = self._absolutize_path(e_path) if terminal else e_path
		return (terminal, f_path, entry.options, entry.post_load_processor)

	def has_asset(
		self, path: str, asset_type_name: str, options: t.Dict[str, t.Any]
	) -> t.Optional[
		t.Tuple[bool, str, t.Optional[t.Dict[str, t.Any]], t.Optional[PostLoadProcessor]]
	]:
		if (at_specific_map := self._asset_maps.get(asset_type_name)):
			if (entry := at_specific_map.paths.get(path)) is not None:
				return self._process_asset_hit(path, entry)

			for regex, entry in at_specific_map.regexes:
				if regex.match(path):
					return self._process_asset_hit(path, entry)

		if (entry := self._unc_asset_map.get(path)) is not None:
			return self._process_asset_hit(path, entry)

		for regex, entry in self._unc_regexes:
			if regex.match(path):
				return self._process_asset_hit(path, entry)

		return None

	def _process_complex_asset_hit(self, path: str, entry: AssetRouterEntry):
		e_path = entry.path
		# TODO: Modify further in case of regex/globs?

		# Path is treated as part of options for complex assets, snuff out any attempt of
		# an entry's options at overriding it and add it in if the entry specifies a
		# different path.

		if entry.options is None:
			if e_path is None:
				r_options = None
			else:
				r_options = {"path": e_path}
		else:
			if e_path is None:
				r_options = entry.options
				if "path" in r_options:
					r_options["path"] = path
			else:
				r_options = entry.options.copy()
				r_options["path"] = e_path

		return (entry.terminal, r_options, entry.post_load_processor)

	def has_complex_asset(
		self, asset_type_name: str, options: t.Dict[str, t.Any]
	) -> t.Optional[t.Tuple[bool, t.Optional[t.Dict[str, t.Any]], t.Optional[PostLoadProcessor]]]:
		if "path" not in options:
			return None

		# TODO: may intransparently make path a string, document this
		path = path_to_string(options["path"])

		if (at_specific_map := self._asset_maps.get(asset_type_name)):
			if (entry := at_specific_map.paths.get(path)) is not None:
				return self._process_complex_asset_hit(path, entry)

			for regex, entry in at_specific_map.regexes:
				if regex.match(path):
					return self._process_complex_asset_hit(path, entry)

		if (entry := self._unc_asset_map.get(path)) is not None:
			return self._process_complex_asset_hit(path, entry)

		for regex, entry in self._unc_regexes:
			if regex.match(path):
				return self._process_complex_asset_hit(path, entry)

		return None

	def has_pyobj(self, ident: t.Hashable) -> t.Tuple[bool, t.Any]:
		if ident in self._pyobj_map:
			return (True, self._pyobj_map[ident])
		return (False, None)

	def get_library_specs(self) -> t.Dict[str, t.Tuple[LibrarySpecPattern, ...]]:
		return self._library_specs

	def discover_libraries(
		self,
		library_specs: t.Dict[str, t.Tuple[LibrarySpecPattern, ...]],
	) -> t.Dict[str, t.Dict[str, t.Sequence[ParameterTuple]]]:
		to_discover = {name: v for name, v in self._library_specs.items() if name in library_specs}
		res = {}
		for n, v in to_discover.items():
			res[n] = self._discover_library(v)
		return res

	def _discover_library(
		self,
		patterns: t.Tuple[LibrarySpecPattern, ...],
	) -> t.Dict[str, t.List[ParameterTuple]]:
		lib_files: t.List[t.Tuple[str, t.Optional[str]]] = []
		for pattern in patterns:
			# Glob by the pattern
			paths = glob.glob(os.path.join(self._dir, pattern.pattern))
			files: t.Set[str] = set()

			# Recursively scan all the directories that the glob ended up delivering.
			# Add the paths relative to self._dir to `files`.
			for path in paths:
				if os.path.isdir(path):
					for rpath in self._scan_dir(path):
						files.add(os.path.relpath(rpath, self._dir))
				elif os.path.isfile(path):
					files.add(os.path.relpath(path, self._dir))

			# Throw out everything matching an exclude pattern
			for exc in pattern.exclude:
				for disqualified in fnmatch.filter(files, exc):
					files.remove(disqualified)
			lib_files.extend((f, pattern.asset_type_name) for f in files)

		# Guess asset types based on extension or just take the one forced by the pattern
		final_result = defaultdict(list)
		for file, asset_type_name in lib_files:
			if asset_type_name is None:
				ext = os.path.splitext(file)[1]
				if not ext or ext[1:].lower() not in _BUILTIN_EXTENSION_MAP:
					continue

				asset_type_name = _BUILTIN_EXTENSION_MAP[ext[1:].lower()]

			final_result[asset_type_name].append(((file,), {}))

		return dict(final_result)

	def _scan_dir(self, p: str) -> t.List[str]:
		res = []
		for e in os.scandir(p):
			if e.is_dir():
				res.extend(self._scan_dir(e.path))
			elif e.is_file():
				res.append(e.path)
		return res


class LoadResult(t.Generic[T]):
	__slots__ = (
		"item",
		"estimated_size_system",
		"estimated_size_gpu",
		"provider_internal_size_system",
		"provider_internal_size_gpu",
	)

	def __init__(
		self,
		item: T,
		estimated_size_system = 0,
		estimated_size_gpu = 0,
		provider_internal_size_system = 0,
		provider_internal_size_gpu = 0,
	) -> None:
		self.item = item
		self.estimated_size_system = estimated_size_system
		"""
		The amount of system memory directly occupied by ``item``.
		"""

		self.estimated_size_gpu = estimated_size_gpu
		"""
		The amount of graphics memory directly occupied by ``item``.
		"""

		self.provider_internal_size_system = provider_internal_size_system
		"""
		The amount of memory ``item`` takes up inside of a RAM cache
		owned by its provider.
		"""

		self.provider_internal_size_gpu = provider_internal_size_gpu
		"""
		The amount of memory ``item`` takes up inside of a VRAM cache
		owned by its provider.
		"""


class BaseAssetProvider(abc.ABC, t.Generic[T]):
	def __init__(self, asm: "AssetSystemManager") -> None:
		self._asm = asm

	@abc.abstractmethod
	def get_estimated_asset_size(self, item: T) -> int:
		raise NotImplementedError()

	@abc.abstractmethod
	def get_cache_usage(self) -> t.Tuple[int, int]:
		raise NotImplementedError()

	@abc.abstractmethod
	def load(self, *_a, **_k) -> t.Any:  # P.args/kwargs retracted
		raise NotImplementedError()

	@abc.abstractmethod
	def unload(self, key: t.Hashable, item: T) -> None:
		raise NotImplementedError()

	@abc.abstractmethod
	def get_loading_steps(self) -> t.Tuple[t.Tuple[t.Callable, bool], ...]:
		raise NotImplementedError()

	@abc.abstractmethod
	def create_cache_key(self, *_a, **_k) -> t.Hashable:  # P.args/kwargs retracted
		raise NotImplementedError()


class AssetProvider(BaseAssetProvider[T]):
	def __init__(self, asm: "AssetSystemManager") -> None:
		super().__init__(asm)
		assert (
			inspect.signature(self.load).replace(return_annotation=None) ==
			inspect.signature(self.create_cache_key).replace(return_annotation=None)
		)

	def get_estimated_asset_size(self, item: T) -> int:
		return 1

	@t.final
	def get_cache_usage(self) -> t.Tuple[int, int]:
		return (0, 0)

	@t.final
	def get_loading_steps(self) -> t.Tuple[t.Tuple[t.Callable, bool]]:
		return ((self.load, True),)

	@abc.abstractmethod
	def load(self, path: str, *_a, **_k) -> T:
		raise NotImplementedError()

	@t.final
	def unload(self, key: t.Hashable, item: T) -> None:
		pass

	@abc.abstractmethod
	def create_cache_key(self, path: str, *_a, **_k) -> t.Hashable:
		raise NotImplementedError()


class CacheAwareAssetProvider(BaseAssetProvider[T]):
	@t.final
	def get_estimated_asset_size(self, item: T) -> int:
		raise RuntimeError("Cannot call this method on cache aware assets.")


class OptionlessAssetProvider(AssetProvider[T]):
	@t.final
	def create_cache_key(self, path: str) -> t.Hashable:
		return path


class BytesAssetProvider(OptionlessAssetProvider[bytes]):
	def load(self, path: str) -> bytes:
		with open(path, "rb") as f:
			return f.read()

	def get_estimated_asset_size(self, item: bytes) -> int:
		try:
			return sys.getsizeof(item)
		except TypeError:
			return 8 + len(item)


class TextAssetProvider(AssetProvider[str]):
	def load(self, path: str, encoding: str = "utf-8") -> str:
		with open(path, "r", encoding=encoding) as f:
			return f.read()

	def create_cache_key(self, path: str, encoding: str = "utf-8") -> t.Hashable:
		return (path, encoding)

	def get_estimated_asset_size(self, item: str) -> int:
		try:
			return sys.getsizeof(item)
		except TypeError:
			# Definitely undershooting when unicode comes into play
			return 8 + len(item)


def _recursive_json_size(item: object) -> int:
	if isinstance(item, dict):
		return (
			sum(_recursive_json_size(k) + _recursive_json_size(v) for k, v in item.items()) +
			sys.getsizeof(item)
		)
	elif isinstance(item, list):
		return sum(_recursive_json_size(i) for i in item) + sys.getsizeof(item)
	return sys.getsizeof(item)


class JSONAssetProvider(AssetProvider[t.Dict]):
	def load(self, path: str, encoding: str = "utf-8") -> str:
		with open(path, "r", encoding=encoding) as f:
			return json.load(f)

	def create_cache_key(self, path: str, encoding: str = "utf-8") -> t.Hashable:
		return (path, encoding)

	def get_estimated_asset_size(self, item: t.Dict) -> int:
		try:
			return _recursive_json_size(item)
		except TypeError:
			return 8


class XMLAssetProvider(OptionlessAssetProvider[ElementTree]):
	def load(self, path: str) -> ElementTree:
		et = ElementTree()
		# NOTE: The xml files contain the encoding inside them, which is mega stupid
		# since you need the encoding to properly parse them, so like ????
		# Unless there is some spec that declares that the first line MUST be valid ASCII
		# and then you have to change the encoding or whatever but i'm not gonna care about
		# all that and just have this work for utf8.
		with open(path, "r", encoding="utf-8") as f:
			et.parse(f, AlmostXMLParser())
		return et

	def get_estimated_asset_size(self, item: ElementTree) -> int:
		try:
			size = sys.getsizeof(item)
			for element in item.iter():
				size += sys.getsizeof(element)
				size += sys.getsizeof(element.tag)
				size += sys.getsizeof(element.tail)
				size += sys.getsizeof(element.text)
				size += sys.getsizeof(element.attrib)
				size += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in element.attrib.items())
			return size
		except TypeError:
			return 8


# TODO: StaticSources produce StaticMemorySources, causing them to not be reported
# as in-use when their data is still referenced by the StaticMemorySource.
# Might want to roll some kind of custom solution that fixes that
class SoundAssetProvider(AssetProvider[Source]):
	_ogg_decoder = ogg_decoder.get_decoders()[0]

	def load(
		self,
		path: str,
		stream: bool = False,
		decoder: t.Optional["MediaDecoder"] = None,
	) -> Source:
		if decoder is None:
			decoder = self._ogg_decoder
		return media.load(path, streaming=stream, decoder=decoder)

	def create_cache_key(
		self, path: str, stream: bool = False, decoder: t.Optional["MediaDecoder"] = None
	) -> t.Hashable:
		if decoder is None:
			decoder = self._ogg_decoder
		return (path, stream, decoder)

	def get_estimated_asset_size(self, item: Source) -> int:
		# Falsify and only report for static sources.
		# Streaming sources shouldn't be cached anyways.
		if isinstance(item, StaticSource):
			try:
				return sys.getsizeof(item) + sys.getsizeof(item._data)
			except TypeError:
				return len(item._data) if item._data is not None else 0
		return 8


class ImageDataAssetProvider(AssetProvider["ImageData"]):
	def load(self, path: str) -> "ImageData":
		return image.load(path)

	def create_cache_key(self, path: str) -> t.Hashable:
		return path

	def get_estimated_asset_size(self, item: "ImageData") -> int:
		size = sys.getsizeof(item, 8)
		if isinstance(item._current_data, bytes):
			try:
				size += sys.getsizeof(item._current_data)
			except TypeError:
				size += len(item._current_data)
		return size


class ImageAssetProvider(CacheAwareAssetProvider[Texture]):
	def __init__(self, asm: "AssetSystemManager") -> None:
		super().__init__(asm)

		# TODO: Atlases may fragment. Possibly add yet another function to Cache-aware asset
		# providers so that they may defragment them. Would require the asset system to pass in
		# all unused textures. Not impossible, just annoying
		self.tex_bin_size = 4096
		make_tex_bin = lambda: TextureBin(self.tex_bin_size, self.tex_bin_size)
		self._hinted_tex_bins: t.Dict[t.Hashable, TextureBin] = defaultdict(make_tex_bin)
		self._hinted_tex_bins[None]

		self._cache_key_to_bin_key_map = {}

		self._texture_cache_size = 0

	def get_loading_steps(self) -> t.Tuple[t.Tuple[t.Callable, bool], ...]:
		return ((self.load, True), (self.load_create_texture, False))

	def get_cache_usage(self) -> t.Tuple[int, int]:
		return (0, self._texture_cache_size)

	def load(
		self,
		cache: bool,
		cache_key: t.Hashable,
		path: str,
		atlas_hint: t.Hashable = None,
	):
		image_data = load_image_data(path, cache=False)

		# HACK: Private access / implementation-copypaste, but saves conversion work that
		# would otherwise stall the main thread for like 300ms at worst.
		target_format_str = image_data.format
		target_pitch = abs(image_data._current_pitch)
		# Second parameter always ends up as GL_UNSIGNED_BYTE, probably safe to not worry about it
		gl_fmt, _ = image_data._get_gl_format_and_type(target_format_str)
		if gl_fmt is None:
			target_format_str = {1: 'R', 2: 'RG', 3: 'RGB', 4: 'RGBA'}[len(target_format_str)]
			gl_fmt, _ = image_data._get_gl_format_and_type(target_format_str)

		new_data = image_data._convert(target_format_str, target_pitch)
		image_data.set_data(target_format_str, target_pitch, new_data)
		# HACK: Remove everything between these two "HACK" comments if it causes problems

		return (image_data, cache, cache_key, atlas_hint), {}

	def load_create_texture(
		self,
		img_data: "ImageData",
		cache: bool,
		cache_key: t.Hashable,
		atlas_hint: t.Hashable,
	) -> LoadResult[Texture]:
		texture = None
		bin_key = None

		if cache and img_data.width <= self.tex_bin_size and img_data.height <= self.tex_bin_size:
			target_bin = self._hinted_tex_bins[atlas_hint]

			bin_size_prev = target_bin.get_area()
			add_result = target_bin.add(img_data)
			if add_result is None:
				logger.warning(f"Failed storing image {img_data} in atlas {atlas_hint}")
			else:
				texture = add_result[0]
				bin_key = (atlas_hint, add_result[1])

				# Textures are rather hardwired to use RGBA8, classic multiply by 4
				self._texture_cache_size += (target_bin.get_area() - bin_size_prev) * 4

		tex_size = img_data.width * img_data.height * 4
		if texture is None:
			bin_key = None
			texture = img_data.get_texture()

		self._cache_key_to_bin_key_map[cache_key] = bin_key

		return LoadResult(
			texture, 0, tex_size * (bin_key is None), 0, tex_size * (bin_key is not None)
		)

	def unload(self, key: t.Hashable, item: Texture) -> None:
		assert key in self._cache_key_to_bin_key_map

		bin_key = self._cache_key_to_bin_key_map.pop(key)

		if bin_key is None:
			# Texture is not atlased, delete directly.
			item.delete()
			return

		# Remove texture from the bin it's allocated in.
		# Might change the bin's size, so update it as well
		bin_ = self._hinted_tex_bins[bin_key[0]]
		bin_size_prev = bin_.get_area()
		bin_.remove(bin_key[1])
		self._texture_cache_size += (bin_.get_area() - bin_size_prev) * 4

	def create_cache_key(self, path: str, atlas_hint: t.Hashable = None) -> t.Hashable:
		# NOTE: Really ugly, but complex assets need to ensure this
		return path_to_string(path)


class FramesAssetProvider(AssetProvider[FrameCollection]):
	def load(self, path: str) -> FrameCollection:
		# Do not cache the xml, only needed for creating the FrameCollection once.
		xml = load_xml(path, cache=False)
		atlas_texture = load_image(Path(path).parent / xml.getroot().attrib["imagePath"])

		texture_region_cache: t.Dict[t.Tuple[int, int, int, int], "AbstractImage"] = {}
		frame_collection = FrameCollection()

		for sub_texture in xml.getroot():
			if sub_texture.tag != "SubTexture":
				logger.warning(f"Expected 'SubTexture' tag, got {sub_texture.tag!r}. Skipping.")
				continue

			if sub_texture.attrib.get("rotated") == "true":
				# TODO: Rotated frames must be rotated CCW by 90°.
				# Possible by just cycling the texture coordinates and
				# then lying about width and height. I think.
				raise NotImplementedError("Rotation isn't implemented, sorry")

			name, x, y, w, h, fx, fy, fw, fh = (
				sub_texture.attrib.get(k) for k in (
					"name", "x", "y", "width", "height", "frameX", "frameY", "frameWidth",
					"frameHeight"
				)
			)
			region = (x, y, w, h)
			frame_vars = (fx, fy, fw, fh)

			if (
				name is None or any(i is None for i in region) or (
					any(i is None for i in frame_vars) and
					any(i is not None for i in frame_vars)
				) # this sucks; basically none of the first five fields may be None and either
				#   all or none of the frame_vars must be None.
			):
				logger.warning(
					f"{(name, region, frame_vars)} Invalid attributes for SubTexture entry. "
					f"Skipping."
				)
				continue

			x, y, w, h = region = tuple(int(e) for e in region)
			fx, fy, fw, fh = frame_vars = tuple(None if e is None else int(e) for e in frame_vars)
			if region not in texture_region_cache:
				texture_region_cache[region] = atlas_texture.get_region(
					x, atlas_texture.height - h - y, w, h,
				)

			trimmed = frame_vars[0] is not None

			frame_collection.add_frame(
				texture_region_cache[region],
				Vec2(fw, fh) if trimmed else Vec2(w, h),
				Vec2(-fx, -fy) if trimmed else Vec2(0, 0),
				name,
			)

		return frame_collection

	def create_cache_key(self, path: str) -> t.Hashable:
		return path


class CacheStats:
	"""
	Cheap dataclass for generic attributes relating to a cache.
	"""

	__slots__ = ("system_memory_used", "gpu_memory_used", "object_count")

	def __init__(self) -> None:
		self.system_memory_used: int = 0
		"""
		The amount of RAM used by the objects in the cache, in bytes.
		This is an estimate and by no means reflects reality.
		"""

		self.gpu_memory_used: int = 0
		"""
		The amount of GPU memory used by textures in the cache, in
		bytes.
		This is an estimate and by no means reflects reality.
		OpenGL implementations have the final say over whether data
		passed to the GPU is resident in RAM or VRAM at any given time.
		"""

		self.object_count: int = 0
		"""
		The amount of distinct assets present in the cache.
		"""

	def copy(self) -> "CacheStats":
		c = CacheStats()
		c.system_memory_used = self.system_memory_used
		c.gpu_memory_used = self.gpu_memory_used
		c.object_count = self.object_count
		return c

	def __eq__(self, o: object) -> bool:
		if isinstance(o, CacheStats):
			return (
				o.system_memory_used == self.system_memory_used and
				o.gpu_memory_used == self.system_memory_used and
				o.object_count == self.object_count
			)
		return NotImplemented


class AssetRequest:
	"""
	Expresses a request for an asset.
	These only make sense when tied to an asset type.
	"""

	# TODO: The ``may_fail`` thing should be expanded by an option for asset routers
	# to index their content. As of now, we can only test for an asset's existence by trying
	# to load it and then catching any error, making it fragile to distinguish between
	# "failed to load" and "does not exist"
	def __init__(
		self,
		args: t.Optional[t.Tuple[t.Any, ...]] = None,
		kwargs: t.Optional[t.Dict[str, t.Any]] = None,
		completion_tag: t.Optional[str] = None,
		may_fail: bool = False,
	) -> None:
		"""

		Args:
			args: The arguments to be passed into an asset type's
				loader function.
			kwargs: The keyword arguments to be passed into an asset type's
				loader funciton.
			completion_tag: An completion tag is used to connect this
				``AssetRequest`` to functions that may use the resulting
				asset to construct more asset requests.
			may_fail: ``AssetRequest``s with this flag set to ``True`` will
				be considered optional, the reason for failure assumed to be
				some kind of file missing.
				This has no effect on actual ``LoadingProcedure``s, but will
				affect functions that determine whether assets need to be
				loaded.
		"""
		self.args = () if args is None else args
		self.kwargs = {} if kwargs is None else kwargs
		self.may_fail = may_fail

		if completion_tag is not None:
			sct = completion_tag.split(".")
			if len(sct) != 2:
				raise ValueError("Bad completion tag, must contain a dot")

			try:
				index = int(sct[1])
			except ValueError as e:
				raise ValueError("Bad completion tag, part behind dot must be an integer") from e

			self.completion_tag = sct[0]
			self.completion_tag_idx = index
		else:
			self.completion_tag = None
			self.completion_tag_idx = None


# Yeah this is good class design
class _ProcessedAssetRequest:
	def __init__(self, asset_type_name: str, base_request: AssetRequest) -> None:
		self.asset_type_name = asset_type_name
		self.args = base_request.args
		self.kwargs = base_request.kwargs
		self.completion_tag = base_request.completion_tag
		self.completion_tag_idx = base_request.completion_tag_idx
		self.may_fail = base_request.may_fail


class LoadingRequest:
	def __init__(
		self,
		asset_requests: t.Dict[str, t.Sequence[AssetRequest]],
		on_load_callbacks: t.Optional[t.Dict[str, t.Callable[..., "LoadingRequest"]]] = None,
		libraries: t.Optional[t.Sequence[str]] = None,
	) -> None:
		self._asset_requests: t.List[_ProcessedAssetRequest] = []

		self.libraries = () if libraries is None else libraries

		completion_tags: t.DefaultDict[str, t.List[_ProcessedAssetRequest]] = defaultdict(list)
		for atn, requests in asset_requests.items():
			for raw_request in requests:
				request = _ProcessedAssetRequest(atn, raw_request)
				self._asset_requests.append(request)

				if request.completion_tag is None:
					continue

				if request.completion_tag_idx in completion_tags[request.completion_tag]:
					raise ValueError(
						"Received two requests competing for the same completion tag index"
					)
				completion_tags[request.completion_tag].append(request)

		for tag, requests in completion_tags.items():
			indices = set(request.completion_tag_idx for request in requests)
			if set(range(max(indices) + 1)) != indices:
				raise ValueError(
					f"Indices for tag {tag!r} didn't form unbroken range starting at 0"
				)
			requests.sort(key=lambda r: r.completion_tag_idx)

		self._completion_tags = dict(completion_tags)
		"""
		Dict mapping each completion tag to a list of its asset
		requests, in proper order.
		"""

		self._on_load_callbacks: t.Dict[t.Callable, t.List[str]] = {}
		"""
		Dict mapping each function to the completion tags it requires,
		as a list.
		"""

		if on_load_callbacks is not None:
			for in_tag_string, callback in on_load_callbacks.items():
				in_tags = in_tag_string.split(",")
				if len(set(in_tags)) != len(in_tags):
					raise ValueError("Duplicate completion tag in callback inlet")
				self._on_load_callbacks[callback] = in_tags

	def is_valid_root_request(self) -> bool:
		"""
		Whether this is a valid root request.
		All inlet tags of all load callbacks must be present in it.
		"""
		for tag_set in self._on_load_callbacks.values():
			for tag in tag_set:
				if tag not in self._completion_tags:
					return False
		return True

	def copy(self) -> "LoadingRequest":
		# TODO gross hack oh man revisit this
		r = LoadingRequest({})
		r._asset_requests = self._asset_requests.copy()
		r._completion_tags = {tag: l.copy() for tag, l in self._completion_tags.items()}
		r._on_load_callbacks = {f: l.copy() for f, l in self._on_load_callbacks.items()}
		r.libraries = list(self.libraries)
		return r

	def add_subrequest(self, other: "LoadingRequest") -> None:
		# Get new asset requests into self._asset_requests
		# Update self._completion_tags
		# Update self._on_load_callbacks
		# Extend self.libraries
		for tag, assets in other._completion_tags.items():
			if tag in self._completion_tags:
				raise ValueError(
					f"Cannot add this request as subrequest, duplicate completion tag {tag!r}"
				)
			self._completion_tags[tag] = assets

		for f, tags in other._on_load_callbacks.items():
			self._on_load_callbacks[f] = tags

		ls = set(self.libraries)
		self.libraries = list(self.libraries) + [l for l in other.libraries if l not in ls]

		self._asset_requests += other._asset_requests


class LoadingProcedureProgress:
	def __init__(self, req: int, lod: int, f: bool, llod: str) -> None:
		self.requested = req
		"""
		The amount of items requested to be loaded.
		This might be zero in case the procedure is empty or has
		just started, don't blindly divide by it.
		Also, see ``requested_final``.
		"""

		self.loaded = lod
		"""
		The amount of items that have successfully been loaded.
		"""

		self.requested_final = f
		"""
		Whether the amount of requested items is final.
		Due to the dynamic nature of loading requests, it can't be
		ascertained at all times.
		If this value is ``False``, any loading screens should
		display an indefinite progress bar or other appropiate symbols.
		"""

		self.last_loaded = llod
		"""
		The asset most recently loaded. Nothing more than a fancy
		string for loading screen decoration.
		"""


class _AssetRequestProgressInfo:
	__slots__ = ("future", "asset", "loaded")

	def __init__(self) -> None:
		self.future: t.Optional[Future] = None
		self.asset: t.Any = None
		self.loaded: bool = False


class _LibraryRequestProgressInfo:
	__slots__ = ("future", "loaded")

	def __init__(self) -> None:
		self.future: t.Optional[Future] = None
		self.loaded: bool = False


class _OnLoadCallbackInfo:
	__slots__ = ("tags", "pending_tags", "called")

	def __init__(self, tags: t.Sequence[str], completed_tags: t.Set[str]) -> None:
		self.tags = tags
		self.pending_tags = set(tags) - completed_tags
		self.called = False


class _CompletionTagInfo:
	__slots__ = ("assets", "remaining", "dependant_callbacks")

	def __init__(self, count: int) -> None:
		self.assets: t.List[t.Any] = [None] * count
		self.remaining = count
		self.dependant_callbacks = set()


class LoadingProcedure:
	"""
	Represents a running AssetSystemManager's loading procedure.
	"""

	def __init__(
		self,
		executor: ThreadPoolExecutor,
		asm: "AssetSystemManager",
		root_request: LoadingRequest,
	) -> None:
		self._executor = executor
		self._asm = asm

		if not root_request.is_valid_root_request():
			raise RuntimeError("Not a root request")

		self._request = LoadingRequest({})

		self._completion_tags: t.Dict[str, _CompletionTagInfo] = {}
		self._on_load_callbacks: t.Dict[t.Callable[..., t.Any], _OnLoadCallbackInfo] = {}

		self._library_requests: t.Dict[str, _LibraryRequestProgressInfo] = {}
		"""
		Maps library requests to their completion state.
		"""

		self._asset_requests: t.Dict[_ProcessedAssetRequest, _AssetRequestProgressInfo] = {}
		"""
		Maps asset requests to their completion state.
		"""

		# These two contain all keys of [library/asset]_requests that have not yet been
		# reported by `_get_new_[asset/library]_requests`.
		self._unreported_libraries: t.List[str] = []
		self._unreported_asset_requests: t.List[_ProcessedAssetRequest] = []

		# Some notes on this lock:
		# It needs to be an RLock in the event that a few `on_done_callback`s run
		# immediately.
		# It is sometimes intentionally not taken when checking for `_cancelled` since
		# cancelled can only move one way and attempts to submit loaders when cancelled
		# just returns None which needs to be checked for.
		self._lock = threading.RLock()

		self._cancelled = False
		self._cancelled_pending_return = 0
		"""
		How many futures still need to finish before the request is
		truly cancelled.
		Valid only when `self._cancelled` is True.
		"""

		self._requested = 0
		self._requested_final = False
		self._loaded = 0
		self._last_loaded_asset = ""

		self.schedule(root_request)

	def cancel(self) -> None:
		"""
		Cancel this ``LoadingProcedure``.
		This does not immediately stop all running loading threads.
		You must wait until calls to ``is_done`` return ``True`` until
		it is safe to start new ones.
		"""
		with self._lock:
			if self._cancelled:
				return

			self._cancelled = True
			for f in self._asset_requests.values():
				if f.future is None or f.future.done():
					continue

				if not f.future.cancel():
					# Future failed cancelling, meaning it's running or just completed because
					# the other thread ran inbetween the last few statements.
					# However, the last case is fine cause that future's thread is now stuck
					# in the callback waiting for this lock, which is why we can safely increment.
					self._cancelled_pending_return += 1

			for f in self._library_requests.values():
				if f.future is None or f.future.done():
					continue

				if not f.future.cancel():
					# See above
					self._cancelled_pending_return += 1

			self._executor.shutdown(wait=False)

	def _on_future_done(self, future: Future) -> None:
		with self._lock:
			if self._cancelled and not future.cancelled():
				# Decrement only if this future was one the procedure had to wait for after
				# being cancelled.
				# Ones that got cancelled normally are fine and not included in the count.
				self._cancelled_pending_return -= 1

	def _submit_asset_loading_job(
		self,
		asset_request: _ProcessedAssetRequest,
		f: t.Callable[..., t.Any],
		*args,
		**kwargs,
	) -> t.Optional[Future]:
		with self._lock:
			if self._cancelled:
				# I guess we could get rid of none checks by introducing some kind of dummy
				# "always cancelled" future, but that's be really ugly, so no
				return None

			future = self._executor.submit(f, *args, **kwargs)
			future.add_done_callback(self._on_future_done)
			self._asset_requests[asset_request].future = future
			return future

	def _submit_library_loading_job(
		self, library_name: str, f: t.Callable[[str], t.Any]
	) -> t.Optional[Future]:
		with self._lock:
			if self._cancelled:
				return None

			future = self._executor.submit(f, library_name)
			future.add_done_callback(self._on_future_done)
			self._library_requests[library_name].future = future
			return future

	def get_progress(self) -> LoadingProcedureProgress:
		with self._lock:
			return LoadingProcedureProgress(
				self._requested,
				self._loaded,
				self._requested_final,
				self._last_loaded_asset,
			)

	def is_done(self) -> bool:
		"""
		Whether the loading procedure has completed.
		No more threads for it are running and it is safe to start
		new ones.
		"""
		with self._lock:
			if self._cancelled:
				# A cancelled LoadingProcedure can be considered done only once
				# none of its futures are left running.
				return self._cancelled_pending_return == 0

			if self._unreported_asset_requests or self._unreported_libraries:
				return False

			return self._requested == self._loaded

	def schedule(self, new_request: LoadingRequest) -> None:
		"""
		Schedule another LoadingRequest on the loading process this
		procedure represents.
		This calls ``add_subrequest`` on the existing request and
		updates this ``LoadingProcedure`` appropiately.
		"""
		with self._lock:
			self._add_more_requests((new_request,))

	def _call_on_load_callback(self, cb: t.Callable) -> LoadingRequest:
		assert not self._on_load_callbacks[cb].pending_tags
		assert not self._on_load_callbacks[cb].called

		args = []
		for tag in self._on_load_callbacks[cb].tags:
			assert self._completion_tags[tag].remaining == 0
			args.extend(self._completion_tags[tag].assets)

		# TODO: should probably errorcheck
		self._on_load_callbacks[cb].called = True
		return cb(*args)

	def _add_more_requests(self, new_requests: t.Iterable[LoadingRequest]) -> None:
		req_queue = list(new_requests)

		while req_queue:
			new_request = req_queue.pop(0)
			if self._requested_final:
				logger.warning("LoadingProcedure finality violated, ignoring request.")
				continue

			try:
				self._request.add_subrequest(new_request)
			except ValueError as e:
				logger.error(f"Failed adding subrequest to loading procedure: {e}")
				return

			for cb, areqs in new_request._completion_tags.items():
				if cb not in self._completion_tags:
					self._completion_tags[cb] = _CompletionTagInfo(len(areqs))

			completed_tags = {tag for tag, i in self._completion_tags.items() if i.remaining == 0}
			for cb, required_tags in new_request._on_load_callbacks.items():
				self._on_load_callbacks[cb] = _OnLoadCallbackInfo(required_tags, completed_tags)
				if not self._on_load_callbacks[cb].pending_tags:
					req_queue.append(self._call_on_load_callback(cb))
				else:
					for pending_ct in self._on_load_callbacks[cb].pending_tags:
						self._completion_tags[pending_ct].dependant_callbacks.add(cb)

			for areq in new_request._asset_requests:
				if areq.completion_tag is not None:
					assert areq.completion_tag in self._completion_tags

				self._requested += 1
				self._asset_requests[areq] = _AssetRequestProgressInfo()
				self._unreported_asset_requests.append(areq)

			for lib_name in new_request.libraries:
				if lib_name not in self._library_requests:
					self._unreported_libraries.append(lib_name)
					self._library_requests[lib_name] = _LibraryRequestProgressInfo()

		self._determine_finality()

	def _determine_finality(self) -> None:
		# Finality can be guaranteed once there's no more pending completion callbacks
		# and all the libraries have been loaded.
		# Kind of relies on the logic of the AssetSystemManager, but that's fine.
		if not self._requested_final:
			if (
				all(x.loaded for x in self._library_requests.values()) and
				all(x.called for x in self._on_load_callbacks.values())
			):
				self._requested_final = True

	def _asset_available(self, asset_request: _ProcessedAssetRequest, asset: t.Any) -> None:
		"""
		An asset request, previously returned by
		``_get_new_asset_requests`` has been resolved to the given
		asset.
		"""
		if len(asset_request.args) > 0 and isinstance(asset_request.args[0], (str, Path)):
			name = asset_request.args[0]
		elif (
			"path" in asset_request.kwargs and
			isinstance(asset_request.kwargs["path"], (str, Path))
		):
			name = asset_request.kwargs["path"]
		else:
			name = str(id(asset_request))

		with self._lock:
			ar_info = self._asset_requests[asset_request]
			ar_info.asset = asset
			ar_info.loaded = True

			self._loaded += 1
			self._last_loaded_asset = f"{asset_request.asset_type_name}:{name}"

			if (comp_tag := asset_request.completion_tag) is None:
				return

			self._completion_tags[comp_tag].assets[asset_request.completion_tag_idx] = asset
			self._completion_tags[comp_tag].remaining -= 1
			if self._completion_tags[comp_tag].remaining != 0:
				return

			to_call = []
			for cb in self._completion_tags[comp_tag].dependant_callbacks:
				self._on_load_callbacks[cb].pending_tags.remove(comp_tag)
				if not self._on_load_callbacks[cb].pending_tags:
					to_call.append(cb)

			new_requests = []
			for cb in to_call:
				new_requests.append(self._call_on_load_callback(cb))

			self._add_more_requests(new_requests)

	# TODO: The distinction between loaded assets/called callbacks and
	# failed assets/retracted callbacks is lacking, but good enough for PNF's usecases
	def _asset_failed_loading(
		self, asset_request: _ProcessedAssetRequest, exc: BaseException
	) -> None:
		"""
		An asset that was requested to be loaded, through
		``_get_new_asset_requests``, failed to load with the given exception.
		"""
		# We have to throw away any completion callbacks that may have depended on this asset
		with self._lock:
			self._asset_requests[asset_request].loaded = True

			self._loaded += 1

			if (comp_tag := asset_request.completion_tag) is None:
				return

			for cb in self._completion_tags[comp_tag].dependant_callbacks:
				self._on_load_callbacks[cb].called = True

			self._determine_finality()

	def _library_available(self, lib_name: str, lib_request: LoadingRequest) -> None:
		"""
		A library previously returned through ``_get_new_library_requests``
		has been resolved and is now available.
		"""
		with self._lock:
			self._library_requests[lib_name].loaded = True
			self._last_loaded_asset = f"lib:{lib_name}"
			self._add_more_requests((lib_request,))

	def _library_failed_loading(self, lib_name, exc: BaseException) -> None:
		with self._lock:
			self._library_requests[lib_name].loaded = True
			self._determine_finality()

	def _get_new_asset_requests(self) -> t.List[_ProcessedAssetRequest]:
		"""
		Not to be used by user code.
		Returns all asset requests that have not yet been returned by
		a call to this method.
		To be used by internal code that schedules the loads.
		"""
		if self._cancelled:
			return []

		with self._lock:
			l = self._unreported_asset_requests
			self._unreported_asset_requests = []
			return l

	def _get_new_libraries(self) -> t.List[str]:
		"""
		Not to be used by user code.
		Returns all library names that have not yet been returned by a
		call to this method.
		"""
		if self._cancelled:
			return []

		with self._lock:
			l = self._unreported_libraries
			self._unreported_libraries = []
			return l


class _CacheEntry(t.Generic[T]):
	"""An cache entry for an asset."""

	__slots__ = (
		"item", "first_requested", "last_requested", "cache_hits", "required_by", "dependencies",
		"estimated_size_system", "estimated_size_gpu", "estimated_provider_usage_system",
		"estimated_provider_usage_gpu"
	)

	def __init__(
		self, load_result: LoadResult[T], dependencies: t.List[AssetIdentifier], age: int
	) -> None:
		self.item = load_result.item
		self.first_requested = age
		self.last_requested = age
		self.cache_hits = 0
		self.required_by: t.Set[AssetIdentifier] = set()
		self.dependencies = dependencies
		self.estimated_size_system = load_result.estimated_size_system
		self.estimated_size_gpu = load_result.estimated_size_gpu
		self.estimated_provider_usage_system = load_result.provider_internal_size_system
		self.estimated_provider_usage_gpu = load_result.provider_internal_size_gpu


class _AssetType(t.Generic[T]):
	def __init__(
		self,
		name: str,
		is_complex: bool,
		is_cache_aware: bool,
		provider: BaseAssetProvider[T],
		loader: t.Callable[..., T],
	) -> None:
		self.name = name
		"""This asset type's name."""

		self.is_complex = is_complex
		"""
		Whether this asset type is complex.
		See ``AssetSystemManager.register_complex_asset_provider``.
		"""

		self.is_cache_aware = is_cache_aware
		"""
		Whether this asset (its provider) is cache-aware.
		See ``AssetSystemManager.register_cache_aware_complex_asset_provider``.
		"""

		self.cache: t.Dict[t.Hashable, _CacheEntry[T]] = {}
		"""
		The asset type's cache. Contains all items created through the
		loader method when ``cache=True``. Hands off, this is managed by
		the ``AssetSystemManager``.
		"""

		self.provider: BaseAssetProvider[T] = provider
		"""The asset type's provider."""

		self.current_provider_cache_memory_usage_system = 0
		"""
		The most recently known amount of memory this provider occupies
		in RAM, as reported by its ``get_cache_usage`` method.
		"""

		self.current_provider_cache_memory_usage_gpu = 0
		"""
		The most recently known amount of GPU memory this provider
		occupies, as reported by its ``get_cache_usage`` method.
		"""

		self.loader: t.Optional[t.Callable[..., T]] = loader
		"""
		The generated loader function for this asset type.
		"""


class EvictionProcessState:
	def __init__(self) -> None:
		self.sys_memory_target = 0
		self.gpu_memory_target = 0
		self.opt_sys_mem_target = 0
		self.opt_gpu_mem_target = 0
		self.memory_targets_required = 0
		self.gc_less_attempts_remaining = 0
		self.completed = True

	def reset(
		self,
		sys_memory_target: t.Optional[int],
		gpu_memory_target: t.Optional[int],
		gc_less_attempts: int,
		optimistic_sweep_stop_factor: float,
	) -> None:
		self.sys_memory_target = sys_memory_target
		self.gpu_memory_target = gpu_memory_target
		self.opt_sys_mem_target = None
		self.gpu_sys_mem_target = None

		self.memory_targets_required = 0

		if sys_memory_target is not None:
			self.memory_targets_required += 1
			self.opt_sys_mem_target = sys_memory_target * optimistic_sweep_stop_factor

		if gpu_memory_target is not None:
			self.memory_targets_required += 1
			self.opt_gpu_mem_target = gpu_memory_target * optimistic_sweep_stop_factor

		self.gc_less_attempts_remaining = gc_less_attempts
		self.completed = False

	def get_result(self, sys_mem_used: int, gpu_mem_used: int) -> "_EvictionResult":
		if not self.completed:  # Shouldnt be called in this state
			raise RuntimeError("Can't get result if the eviction is still going")

		return _EvictionResult(
			None if self.sys_memory_target is None else sys_mem_used <= self.sys_memory_target,
			None if self.gpu_memory_target is None else gpu_mem_used <= self.gpu_memory_target,
		)


class _EvictionResult:
	def __init__(self, succeeded_sys: t.Optional[bool], succeeded_gpu: t.Optional[bool]) -> None:
		self.succeeded = not any(i is False for i in (succeeded_sys, succeeded_gpu))
		self.ran_for_sys = succeeded_sys is not None
		self.succeeded_sys = succeeded_sys
		self.ran_for_gpu = succeeded_gpu is not None
		self.succeeded_gpu = succeeded_gpu


class _EvictionSweepStopReason(enum.IntEnum):
	EXHAUSTED = 0
	OPTIMISTIC = 1
	SUCCEEDED = 2


class AssetSystemManager:
	"""
	# TODO
	"""

	def __init__(self, pyglet_clock: clock.Clock) -> None:
		self._clock = pyglet_clock

		self._cwd = Path.cwd()

		self.asset_router_stack: t.List[BaseAssetRouter] = []
		self.asset_type_registry: t.Dict[str, _AssetType] = {}
		self._pyobj_cache: t.Dict[t.Hashable, t.Any] = {}

		self._memory_usage_stats = CacheStats()

		self.age = 0

		self._cache_lock = threading.Lock()
		"""
		A lock that must be held when manipulating the asset cache, or
		the memory usage statistics object, or just anything that may
		cause a race condition between loader threads.
		"""

		# TODO: make configurable
		# NOTE: 4 threads max since they're all still pretty likely to run a good amount of
		# python bytecode in the generated loader methods.
		# Don't want them to starve the main or media thread too much.
		self._loader_thread_count = 4

		# Tbh i think this lock is really pointless
		self.loading_procedure_management_lock = threading.Lock()
		self._running_loading_procedures: t.List[LoadingProcedure] = []

		self._eviction_lock = threading.Lock()

		self._eviction_gate = threading.Event()
		"""
		All generated loaders will have to "pass" this gate.
		This serves as not much more than a bandaid, but i guess it
		doesn't hurt: If an eviction is scheduled/running, the cache has
		filled up and in order to prevent memory peaking out by yet more
		loaders getting data and holding onto it before they can interact
		with the cache, the gate is closed.
		"""
		self._eviction_gate.set()

		self._raised_limit_gpu = 0
		self._raised_limit_sys = 0

		# TODO: Make everything below this comment configurable
		self._enable_automatic_eviction = True

		self._eviction_limit_extension_sys = 2**26
		"""
		If an eviction fails to clear memory to the demanded target,
		the eviction limit is temporarily raised to the amount of
		occupied memory plus this value.

		This helps to reduce frequent eviction attemps that are all
		doomed to fail in the event that a large amount of assets have
		to be loaded that simply exceed the cache size limit.

		The limit extension will decay in
		``self._eviction_limit_extension_decay`` clean steps for each
		newly loaded asset.
		"""

		self._eviction_limit_extension_gpu = 2**26
		"""
		See ``self._eviction_limit_extension_sys``, same deal here.
		"""

		self._eviction_limit_extension_decay = 8
		"""
		Usage of this is explained in
		``self._eviction_limit_extension_sys``.
		"""

		self._sys_memory_limit = 2**30 # 1024MiB
		"""
		At which point of system memory usage to attempt an eviction.
		"""

		self._gpu_memory_limit = 2**31 # 2048MiB
		"""
		At which point of gpu memory usage to attempt an eviction.
		"""

		self._eviction_shrink_factor = 0.85
		"""
		An eviction will attempt to get usage of the triggering memory
		type down to the triggering memory's limit, multiplied by this
		factor.
		"""

		self._optimistic_sweep_stop_factor = 0.9
		"""
		An eviction sweep will be stopped if - assuming the best case
		of all asset trees whose top-level assets have been removed
		being successfully evicted in their entirety - the amount of
		memory that would be then occupied is less or equal to
		``self._x_memory_limit * self._eviction_shrink_factor * \
		  self._optimistic_sweep_stop_factor``.

		Set to 0.0 to easily ruin chances of retaining low-burden
		assets in cache.

		Set to 1.0 to frequently stop sweeps. Preserves cached items
		the best, but might be a bit more processing-intensive and also
		tend to run more garbage collections.
		Also see ``self._bring_gc_closer_on_optimistic_sweep_stop``.
		"""

		self._eviction_safe_burden = 4096.0
		"""
		Assets with a burden score of less than this value will never
		be evicted.
		Theoretically, this allows to clog the asset cache up with
		thousands of extremely small assets as long as they are somewhat
		frequently used, but that is a super-duper unrealistic scenario.
		"""

		self._eviction_use_gc = True
		"""
		Whether to use garbage collections as part of an eviction.
		Very much recommended, otherwise uncollected scenes hogging
		large resources are frequent.
		"""

		self._eviction_gc_less_sweeps = 3
		"""
		Evictions will start running a collection after this many sweeps
		have passed without eviction success.
		Note that they will also activate GC when the eviction is otherwise
		failing.
		"""

		# TODO: not implemented, might be pointless/can be changed into some other method
		# FA&FO, there's no right answers
		self._bring_gc_closer_on_optimistic_sweep_stop = False

		self.eviction_consideration_age = 1
		"""
		How many generations an asset has to be unused for to be
		considerable for eviction.

		``1`` by default, meaning assets from the current generation
		will never be evicted.
		Setting to zero is inadvisable, as eviction might happen too
		quickly, especially in the context of a threaded loading
		procedure.
		"""

		self.eviction_stale_age = 5
		"""
		An asset will be considered stale and be evicted with high
		likelihood if it has not been requested for this many
		generations.
		"""
		# TODO: make everything above this comment configurable

		self._eviction_process_state = EvictionProcessState()
		self._eviction_process_flag = threading.Event()
		"""
		Used to communicate between the eviction and main thread, as
		actual asset eviction has to happen on the main one.
		"""

		self._eviction_cur_limit_extensions_sys: t.List[int] = []
		self._eviction_cur_limit_extensions_gpu: t.List[int] = []

		self._resolved_libraries: t.Dict[str, t.Dict[str, t.Sequence[ParameterTuple]]] = {}
		self._library_specs: t.Dict[str, t.Tuple[LibrarySpecPattern, ...]] = {}

		self._threadloc = threading.local()
		"""
		Thread-local data. Contains:
			`loading_stack`: Aids in tracking of assets dependencies.

			`threaded_load`: Whether the thread is primary or operates
				for a threaded loading procedure.

			`relay_queue`: A one-element queue used to communicate between
				stages of a fragmented loading procedure
		"""
		self._threadloc.loading_stack = []
		self._threadloc.threaded_load = False
		self._threadloc.relay_queue = queue.Queue(1)

	def set_default_asset_directory(self, path: Path) -> None:
		"""
		Sets the default directory that paths are absolutized with when
		no AssetRouter was found for them. By default, the working
		directory at the time the AssetSystemManager was created is
		used.
		"""
		self._cwd = path

	def get_cache_stats(self) -> CacheStats:
		"""
		Returns the guessed amount of system memory the cached assets
		are currently taking up, as well as the amount of them.
		"""
		return self._memory_usage_stats.copy()

	def _lookup_cache_key(
		self, asset_type_name: str, key: t.Hashable, bump: bool = True
	) -> t.Tuple[bool, t.Any]:
		"""
		Looks up the given asset identifier and returns a two-element
		tuple where [0] denotes whether the asset is encached and [1]
		contains the asset, if it was cached.

		``bump`` specifies whether to update eviction parameters,
		acting as if the asset was retrieved by a standard load call.
		``True`` by default.
		"""
		# My hope is the cache lock ensures that the item cannot be evicted as the reference
		# created by building the tuple will make the sys.getrefcount call fail afterwards.
		with self._cache_lock:
			c = self.asset_type_registry[asset_type_name].cache
			if key in c:
				if bump:
					c[key].last_requested = self.age
					c[key].cache_hits += 1
				return (True, c[key].item)

		return (False, None)

	def _encache(self, asset_type_name: str, key: t.Hashable, load_result: LoadResult) -> None:
		# print("Encaching", asset_type_name, key)

		asset_type = self.asset_type_registry[asset_type_name]

		identifier = (asset_type_name, key)

		ce = _CacheEntry(load_result, self._threadloc.loading_stack[-1][1], self.age)
		# print(f"Dependencies of {identifier} are {ce.dependencies}")

		assert (
			ce.estimated_size_system + ce.estimated_provider_usage_system +
			ce.estimated_size_gpu + ce.estimated_provider_usage_gpu
		) > 0

		if len(self._threadloc.loading_stack) > 1:
			# print(f"Noted {self._threadloc.loading_stack[-2][0]} as dependant on {identifier}.")
			ce.required_by.add(self._threadloc.loading_stack[-2][0])
			self._threadloc.loading_stack[-2][1].append(identifier)

		with self._cache_lock:
			asset_type.cache[key] = ce

			# The provider (only cache-aware ones) may have different memory usage stats now, so
			# go ahead and update them, merging into the total memory usage.
			# Ignore provider_internal memory usage, as a provider may allocate larger pools of
			# memory for the assets interned there.
			pcs, pcg = asset_type.provider.get_cache_usage()
			self._memory_usage_stats.object_count += 1
			self._memory_usage_stats.system_memory_used += (
				ce.estimated_size_system +
				(pcs - asset_type.current_provider_cache_memory_usage_system)
			)
			self._memory_usage_stats.gpu_memory_used += (
				ce.estimated_size_gpu +
				(pcg - asset_type.current_provider_cache_memory_usage_gpu)
			)

			asset_type.current_provider_cache_memory_usage_system = pcs
			asset_type.current_provider_cache_memory_usage_gpu = pcg

		if not self._enable_automatic_eviction:
			return

		# Determine whether to start an eviction.
		# Reduce possibly existing limit extensions beforehand and obey that.

		# NOTE: This lock might be applied way too broadly, but the eviction is a heavily
		# bottlenecking process anyways so who cares
		with self._eviction_lock:
			effective_memory_limit_sys = self._sys_memory_limit
			if self._eviction_cur_limit_extensions_sys:
				effective_memory_limit_sys += self._eviction_cur_limit_extensions_sys.pop()
				logger.trace(
					f"Reduced RAM limit to {(effective_memory_limit_sys) // 1024} KiB"
				)

			effective_memory_limit_gpu = self._gpu_memory_limit
			if self._eviction_cur_limit_extensions_gpu:
				effective_memory_limit_gpu += self._eviction_cur_limit_extensions_gpu.pop()
				logger.trace(
					f"Reduced VRAM limit to {(effective_memory_limit_gpu) // 1024} KiB"
				)

			evict_sys_ram = (
				(ce.estimated_size_system > 0 or ce.estimated_provider_usage_system > 0) and
				self._memory_usage_stats.system_memory_used > effective_memory_limit_sys
			)
			evict_vram = (
				(ce.estimated_size_gpu > 0 or ce.estimated_provider_usage_gpu > 0) and
				self._memory_usage_stats.gpu_memory_used > effective_memory_limit_gpu
			)

			l = []
			if evict_sys_ram:
				l.append("RAM")
			if evict_vram:
				l.append("VRAM")
			if not l:
				return

			logger.info(f"Exceeding {'+'.join(l)} limit, starting eviction")

			_start_time = perf_counter()
			self._eviction_gate.clear()

			eviction_res = self._evict(evict_sys_ram, evict_vram)

			self._eviction_gate.set()
			logger.info(
				f"Eviction {'succeeded' if eviction_res.succeeded else 'failed'} after "
				f"{perf_counter() - _start_time:>.4f}s"
			)

			if eviction_res.succeeded:
				return

			# Eviction failed (but may have freed something), add limit.
			# Existing limit extension will be replaced with the new one.
			if eviction_res.succeeded_sys is False:
				new_limit = (
					max(self._memory_usage_stats.system_memory_used, effective_memory_limit_sys) +
					self._eviction_limit_extension_sys
				)
				diff = new_limit - self._sys_memory_limit
				assert diff > 0

				self._eviction_cur_limit_extensions_sys = [
					int(diff * (i / self._eviction_limit_extension_decay))
					for i in range(1, self._eviction_limit_extension_decay + 1)
				]
				self._eviction_cur_limit_extensions_sys.append(new_limit)
				logger.trace(
					f"RAM eviction limit raised to "
					f"{(self._sys_memory_limit + new_limit) // 1024} KiB"
				)

			if eviction_res.succeeded_gpu is False:
				new_limit = (
					max(self._memory_usage_stats.gpu_memory_used, effective_memory_limit_gpu) +
					self._eviction_limit_extension_gpu
				)
				diff = new_limit - self._gpu_memory_limit
				assert diff > 0

				self._eviction_cur_limit_extensions_gpu = [
					int(diff * (i / self._eviction_limit_extension_decay))
					for i in range(1, self._eviction_limit_extension_decay + 1)
				]
				self._eviction_cur_limit_extensions_gpu.append(new_limit)
				logger.trace(
					f"VRAM eviction limit raised to "
					f"{(self._gpu_memory_limit + new_limit) // 1024} KiB"
				)

	def _remove_from_cache(self, asset_type_name: str, key: t.Hashable) -> None:
		asset_type = self.asset_type_registry[asset_type_name]

		removed_entry = asset_type.cache.pop(key)
		removed_ident = (asset_type_name, key)
		asset_type.provider.unload(key, removed_entry.item)

		for n, k in removed_entry.dependencies:
			self.asset_type_registry[n].cache[k].required_by.remove(removed_ident)

		pcs, pcg = asset_type.provider.get_cache_usage()

		# Provider should now report equal or less memory than what was
		# recorded in the AssetType

		# Adjust metrics based on memory occupied by the item itself and provider difference
		freed_sys = (
			removed_entry.estimated_size_system +
			(asset_type.current_provider_cache_memory_usage_system - pcs)
		)
		freed_gpu = (
			removed_entry.estimated_size_gpu +
			(asset_type.current_provider_cache_memory_usage_gpu - pcg)
		)
		self._memory_usage_stats.object_count -= 1
		self._memory_usage_stats.system_memory_used -= freed_sys
		self._memory_usage_stats.gpu_memory_used -= freed_gpu

		# print(
		# 	f"Evicted {asset_type_name} {key}\n"
		# 	f"  That freed up {freed_sys}B real RAM / "
		# 	f"{removed_entry.estimated_provider_usage_system}B provider-owned RAM, "
		# 	f"{freed_gpu}B real VRAM, {removed_entry.estimated_provider_usage_gpu}B "
		# 	f"provider-owned VRAM"
		# )

		asset_type.current_provider_cache_memory_usage_system = pcs
		asset_type.current_provider_cache_memory_usage_gpu = pcg

	def _calculate_burden_dict(self, asset_type_name: str, ck: t.Hashable):
		# Trees out of multiple elements (pretty rare) will have their eviction parameters
		# treated as a compound of their nodes.

		entry = self.asset_type_registry[asset_type_name].cache[ck]
		burden_dict = {
			"size_sys": entry.estimated_size_system + entry.estimated_provider_usage_system,
			"size_gpu": entry.estimated_size_gpu + entry.estimated_provider_usage_gpu,
			"last_requested": entry.last_requested,
			"immediate_dependencies": 0,
			"full_dependencies": 0,
		}

		# Not propagating last_requested. We don't as you can easily consider a top-level
		# asset the sole interface to its dependencies. If it falls away, no point in
		# keeping its dependencies alive if it was the only thing that ever accessed them.
		# (Plus, less code that way)

		for dep_ident in self.asset_type_registry[asset_type_name].cache[ck].dependencies:
			dep_burden_dict = self._calculate_burden_dict(*dep_ident)
			burden_dict["immediate_dependencies"] += 1
			# TODO: This will duplicate counts on diamond dependencies
			# We don't have those right now, but it's really bad nonetheless
			burden_dict["full_dependencies"] += dep_burden_dict["full_dependencies"]
			burden_dict["size_sys"] += dep_burden_dict["size_sys"]
			burden_dict["size_gpu"] += dep_burden_dict["size_gpu"]

		return burden_dict

	def _weigh_burden(self, b):
		# TODO: May want to use cache_hits as well to prefer assets not requested as much.
		# Considering that can be falsified easily by just having poor code that calls load_x
		# often and relies on the cache though, make its impact minimal

		unused_for = self.age - b["last_requested"]
		size_factor = 1.0
		if unused_for <= 1:
			size_factor = 1.0
		elif unused_for > self.eviction_stale_age:
			size_factor = 999999999999.0
		else:
			# Make Euler spin in his grave and completely misuse the fancy normal distribution
			# curve between 1..unused_cutoff
			# sigma found by guessing, it's 1.7
			q = ndist_1(1.0, 1.7)
			v = ndist_1(float(unused_for), 1.7)
			# TODO: These numbers explode pretty quickly, so quickly that they might overshadow
			# the burden factor given by the stale generation limit.
			# Might look into expanding the comparison key into a tuple that has 0 as first
			# element for non-stale assets, but their respective age for others.
			if v == 0.0:
				# who knows what those floats are up to
				v = 0.000000000001
			# size_factor = 1.0 / ((1.0/q) * v)
			size_factor = min(q / v, 999999999999.0)

		# Calculate how much of a burden an asset is
		# Larger assets should be more targeted for eviction simply cause they fill a lot of
		# memory, but even more so ones that have not been used for some time
		# `size_factor` should explode to pretty high values after an asset was unused for 4
		# generations or so

		return size_factor

	def _evict(self, evict_sys_ram: bool, evict_vram: bool) -> _EvictionResult:
		"""
		Run and complete a cache eviction. May be called from any
		thread, should be called from within a generated loader.
		"""
		# TODO: that's a silly limitation, it makes sense to hand control
		# over to manual eviction. look into something like that.
		if not evict_sys_ram and not evict_vram:
			return _EvictionResult(None, None)

		self._eviction_process_state.reset(
			int(self._sys_memory_limit * self._eviction_shrink_factor) if evict_sys_ram else None,
			int(self._gpu_memory_limit * self._eviction_shrink_factor) if evict_vram else None,
			self._eviction_gc_less_sweeps,
			self._optimistic_sweep_stop_factor,
		)

		# Because i'm not implementing a manual refcounter, we can only reliably process top-level
		# assets per sweep.

		# NOTE: By creative usage of lambdas and the likes, scenes can live longer than they
		# should, which might make them hold on to heavy resources that aren't being used
		# anymore. Running a full garbage collection feels like overkill, but it is in fact
		# capable of getting rid of references to expensive images and the like.
		# We start running those after two cycles that haven't yielded sufficient cleanup.

		# Evict until we understepped all values we care about.
		# Eviction scheme goes:
		# - Get the eviction list and sort them depending on which memory types to clear.
		# - Throw out the most undesirable assets
		#   - In case of a tree, act optimistically! This prevents top-level tiny items from
		#     being evicted in the first sweep: Stop the sweep once a tree would in theory
		#     satisfy eviction requirements. (See `_optimistic_sweep_stop_factor`.)
		#   - Stop the sweep if we're absolutely done clearing out all the memory needed.
		# - The sweep is done.
		#   - If everything's been cleared out and that wasn't enough, tough luck. Done.
		#   - If there have been trees that only just had a bit off the top, retry.
		#   - If we've been through this two times already, start running an expensive GC.

		# TODO: Building the trees all the time can definitely be avoided, but in the end
		# some linear operations and a sort across 200 objects max are just not that much.

		while not self._eviction_process_state.completed:
			if self._eviction_process_state.gc_less_attempts_remaining == 0:
				logger.trace("Running garbage collection for asset eviction. This may stall.")
				gc.collect()  # generation=2

			with self._cache_lock:
				evictable_toplevel_assets = set()
				for at in self.asset_type_registry.values():
					for ck, ce in at.cache.items():
						if any(a == (at.name, ck) for a, _ in self._threadloc.loading_stack):
							# The eviction process may be run by an asset which is being loaded as
							# a dependency of another asset.
							# Since this asset will have an incomplete dependency tree (the asset
							# being loaded does not exist yet), ignore it
							# print(
							# 	"not considering", at.name, ck, "for eviction: in loading stack"
							# )
							continue

						# TODO: could probably prevent full iteration by storing toplevel assets
						if ce.required_by:
							# print("not considering", at.name, ck, "for eviction: not top-level")
							continue

						if self.eviction_consideration_age > (self.age - ce.last_requested):
							# print(
							# 	"not considering", at.name, ck, "for eviction: used too recently"
							# )
							continue

						rc = sys.getrefcount(ce.item) - 1
						if rc != 1:
							# print(
							# 	"not considering", at.name, ck, "for eviction: in use. "
							# 	"refcount ==", rc
							# )
							continue

						evictable_toplevel_assets.add((at.name, ck))

				eviction_list = []
				for identifier in evictable_toplevel_assets:
					d = self._calculate_burden_dict(*identifier)
					relevant_size = d["size_sys"] * evict_sys_ram + d["size_gpu"] * evict_vram

					# When we should clean up only RAM, don't care about VRAM of course, and
					# vice-versa.
					# If there's assets that occupy space in both (somehow?), there's no real
					# point in protecting the memory type that isn't used, just judge them by
					# combined sizes.
					# However, it's possible a sweep goes too far and then evicts a bunch of RAM
					# objects simply because VRAM is overcrowded. We exclude objects based on
					# that, which is the primary reason their size may not be 0.
					if relevant_size == 0:
						# print(f"not considering {identifier} for eviction: relevant size == 0")
						continue

					burden_score = relevant_size * self._weigh_burden(d)
					if burden_score <= self._eviction_safe_burden:
						# print(
						# 	f"not considering {identifier} for eviction: below safe burden score"
						# )
						continue

					eviction_list.append((identifier, d, burden_score))

				if not eviction_list:
					if self._eviction_process_state.gc_less_attempts_remaining > 0:
						logger.trace("Out of evictable items, retrying with gc")
						self._eviction_process_state.gc_less_attempts_remaining = 0
					else:
						logger.trace("Out of evictable items, eviction unsuccessful.")
						self._eviction_process_state.completed = True
					continue

				eviction_list.sort(key = lambda x: x[2], reverse=True)

				# self._dump_eviction_list(eviction_list)

				if self._threadloc.threaded_load:
					self._eviction_process_flag.clear()
					self._clock.schedule_once(self._run_eviction_sweep, 0.0, eviction_list)
					self._eviction_process_flag.wait()
				else:
					self._run_eviction_sweep(None, eviction_list)

		return self._eviction_process_state.get_result(
			self._memory_usage_stats.system_memory_used, self._memory_usage_stats.gpu_memory_used
		)

	def _run_eviction_sweep(
		self, _, list_: t.Iterable[t.Tuple[AssetIdentifier, t.Dict, float]]
	) -> None:
		memory_targets_required = self._eviction_process_state.memory_targets_required

		sys_mem_target = self._eviction_process_state.sys_memory_target
		gpu_mem_target = self._eviction_process_state.gpu_memory_target
		opt_sys_mem_target = self._eviction_process_state.opt_sys_mem_target
		opt_gpu_mem_target = self._eviction_process_state.opt_gpu_mem_target

		optimistic_sys_usage = self._memory_usage_stats.system_memory_used
		optimistic_gpu_usage = self._memory_usage_stats.gpu_memory_used

		had_trees = False
		stop_reason: t.Optional[_EvictionSweepStopReason] = None

		for ident, bd, _ in list_:
			if bd["immediate_dependencies"] > 0:
				had_trees = True

			self._remove_from_cache(*ident)

			# This may be a tree, subtract all of its size.
			# Helps to prevent clearing of low-burden assets in case the entire tree can be taken
			# down over the next sweeps.
			# Problem: We don't want to stop the sweep too fast (in case the tree's subresources
			# actually turn out to not be evictable) and also not run over too many low-burden
			# assets.
			optimistic_sys_usage -= bd["size_sys"]
			optimistic_gpu_usage -= bd["size_gpu"]

			targets_completed = 0
			targets_completed_opt = 0
			if sys_mem_target is not None:
				if self._memory_usage_stats.system_memory_used <= sys_mem_target:
					targets_completed += 1
				if optimistic_sys_usage <= opt_sys_mem_target:
					targets_completed_opt += 1

			if gpu_mem_target is not None:
				if self._memory_usage_stats.gpu_memory_used <= gpu_mem_target:
					targets_completed += 1
				if optimistic_gpu_usage <= opt_gpu_mem_target:
					targets_completed_opt += 1

			if targets_completed == memory_targets_required:
				stop_reason = _EvictionSweepStopReason.SUCCEEDED
				break

			if targets_completed_opt == memory_targets_required:
				# logger.trace("Eviction sweep stopped, optimistic target fulfilled")
				stop_reason = _EvictionSweepStopReason.OPTIMISTIC
				break
		else:
			stop_reason = _EvictionSweepStopReason.EXHAUSTED

		logger.trace(f"Eviction sweep done: {stop_reason.name}")

		decrement_gc = False
		if stop_reason is _EvictionSweepStopReason.SUCCEEDED:
			self._eviction_process_state.completed = True

		elif stop_reason is _EvictionSweepStopReason.OPTIMISTIC:
			assert had_trees
			if self._bring_gc_closer_on_optimistic_sweep_stop:
				decrement_gc = True

		elif stop_reason is _EvictionSweepStopReason.EXHAUSTED:
			if had_trees:
				decrement_gc = True
			else:
				if self._eviction_process_state.gc_less_attempts_remaining > 0:
					logger.trace(
						"Eviction sweep done and no more trees, enabling garbage collection "
						"now for final sweep."
					)
					self._eviction_process_state.gc_less_attempts_remaining = 0
				else:
					self._eviction_process_state.completed = True
		else:
			raise RuntimeError("unreachable")

		if decrement_gc and self._eviction_process_state.gc_less_attempts_remaining > 0:
			if self._eviction_process_state.gc_less_attempts_remaining == 1:
				logger.trace("Enabling garbage collection for next eviction sweeps")
			self._eviction_process_state.gc_less_attempts_remaining -= 1

		self._eviction_process_flag.set()

	def _dump_eviction_list(self, el) -> None:
		print("===== Up for eviction (burden score, type, cache key):")
		for (at_name, ck), _, burden_score in el:
			print(f"{burden_score:>14.2f} {at_name:<16} # {ck}")
		print("=====")

	def advance_age(self) -> None:
		"""
		Advances the age of the AssetSystemManager. This should be called at
		points where the underlying program undergoes a significant change in
		loaded assets, such as leaving a gameworld in favor of another with
		wildly different assets, before starting to load the new assets.
		This aids in considerations for which assets to unload.
		"""
		self.age += 1

	def start_threaded_load(self, request: LoadingRequest) -> LoadingProcedure:
		"""
		Start loading a multitude of items.

		By the end of it, all specified items will be in the cache and should
		be available quickly via their respective ``load`` methods.

		vvv NOT IMPLEMENTED vvv
		As part of such a loading process, the AssetSystemManager will
		attempt to clear the cache of unused items below a certain threshold
		[TODO what threshold lol]
		[AND IMPLEMENT HOUSKEEPING AND ACTUAL ASSET RELEASE BUT LATER]
		"""
		def _tinit():
			self._threadloc.loading_stack = []
			self._threadloc.threaded_load = True
			self._threadloc.relay_queue = queue.Queue()
		executor = ThreadPoolExecutor(self._loader_thread_count, "AssetLoader", _tinit)

		with self.loading_procedure_management_lock:
			lproc = LoadingProcedure(executor, self, request)
			self._running_loading_procedures.append(lproc)

		self._drain_loading_procedure(lproc)
		return lproc

	def _drain_loading_procedure(self, lproc: LoadingProcedure) -> None:
		"""
		Given a ``LoadingProcedure``, asks it for all pending library
		and asset requests and, depending on whether they're
		discovered/cached, immediately passes them to it or starts new
		loading threads on its executor which pass them once they're
		done.

		If the procedure is done by the end of this call, removes it
		from ``_running_loading_procedures``.
		"""
		for lib_name in lproc._get_new_libraries():
			if lib_name in self._resolved_libraries:
				lproc._library_available(lib_name, self._libraries_to_subrequest((lib_name,)))
			else:
				self._start_threaded_library_load(lproc, lib_name)

		while True:
			new_requests = lproc._get_new_asset_requests()
			if not new_requests:
				break

			for asset_request in new_requests:
				is_cached, asset = self._asset_request_check_cache(asset_request)
				if is_cached:
					lproc._asset_available(asset_request, asset)
				else:
					self._start_threaded_asset_request_load(lproc, asset_request)

		if lproc.is_done():
			with self.loading_procedure_management_lock:
				self._running_loading_procedures.remove(lproc)

	def _start_threaded_asset_request_load(
		self,
		lproc: LoadingProcedure,
		asset_request: _ProcessedAssetRequest,
	) -> None:
		future = lproc._submit_asset_loading_job(
			asset_request,
			self.asset_type_registry[asset_request.asset_type_name].loader,
			*asset_request.args,
			**asset_request.kwargs,
		)
		if future is not None:
			future.add_done_callback(
				lambda future, lproc=lproc, asset_request=asset_request:
					self._on_threaded_asset_request_load_complete(future, lproc, asset_request)
			)

	def _on_threaded_asset_request_load_complete(
		self,
		future: Future,
		lproc: LoadingProcedure,
		asset_request: _ProcessedAssetRequest,
	) -> None:
		if future.cancelled():
			# Twitter got to us, no asset available, return
			return

		if (exc := future.exception()) is not None:
			if not asset_request.may_fail:
				logger.error(f"Threaded asset load: {exc}")
			lproc._asset_failed_loading(asset_request, exc)
			return

		# Tell the LoadingProcedure of the asset, then get possibly new ones and schedule
		# loading for them as well.
		lproc._asset_available(asset_request, future.result())
		self._drain_loading_procedure(lproc)

	def _start_threaded_library_load(self, lproc: LoadingProcedure, library_name: str) -> None:
		future = lproc._submit_library_loading_job(library_name, self.load_library)
		if future is not None:
			future.add_done_callback(
				lambda future, lproc=lproc, lib_name=library_name:
					self._on_threaded_library_load_complete(future, lproc, lib_name)
			)

	def _on_threaded_library_load_complete(
		self,
		future: Future,
		lproc: LoadingProcedure,
		lib_name: str,
	) -> None:
		if future.cancelled():
			return

		if (exc := future.exception()) is not None:
			logger.error(f"Threaded library load: {exc}")
			lproc._library_failed_loading(lib_name, exc)
			return

		lproc._library_available(lib_name, self._libraries_to_subrequest((lib_name,)))
		self._drain_loading_procedure(lproc)

	def _asset_request_check_cache(self, request: _ProcessedAssetRequest) -> t.Tuple[bool, t.Any]:
		"""
		Tests whether fulfilling the given asset request would hit the
		cache.
		"""
		asset_type = self.asset_type_registry[request.asset_type_name]

		# This `path` stringification is the worst
		args = request.args
		kwargs = request.kwargs
		if not asset_type.is_complex:
			if "path" in request.kwargs:
				kwargs = request.kwargs.copy()
				kwargs["path"] = path_to_string(kwargs["path"])
			else:
				if len(args) >= 1:  # Otherwise invalid probably
					args = (path_to_string(args[0]),) + args[1:]

		return self._lookup_cache_key(
			asset_type.name,
			asset_type.provider.create_cache_key(*args, **kwargs),
		)

	def _libraries_to_subrequest(self, library_names: t.Iterable[str]) -> LoadingRequest:
		"""
		Turns a number of resolved libraries into a ``LoadingRequest``.
		"""
		lib_subrequests = defaultdict(list)
		for lib_name in library_names:
			for asset_type_name, paramtups in self._resolved_libraries[lib_name].items():
				lib_subrequests[asset_type_name].extend(AssetRequest(*x) for x in paramtups)

		return LoadingRequest(dict(lib_subrequests))

	def requires_loading_process(self, loading_request: LoadingRequest) -> bool:
		"""
		Returns whether a LoadingRequest needs to make calls to load assets,
		which is the case if any of its requested assets/libraries or any of
		its subrequest's assets/libraries are not cached.
		"""
		request = loading_request.copy()

		fake_proc = LoadingProcedure(None, self, request)

		procedure_might_be_drainable = True
		while procedure_might_be_drainable:
			procedure_might_be_drainable = False

			new_libs = fake_proc._get_new_libraries()
			for lib_name in new_libs:
				if lib_name in self._resolved_libraries:
					procedure_might_be_drainable = True
					fake_proc._library_available(
						lib_name, self._libraries_to_subrequest((lib_name,))
					)
				else:
					return True

			new_areqs = fake_proc._get_new_asset_requests()
			for areq in new_areqs:
				ck = self._asset_request_check_cache(areq)
				if ck[0]:
					procedure_might_be_drainable = True
					fake_proc._asset_available(areq, ck[1])
				else:
					if areq.may_fail:
						fake_proc._asset_failed_loading(areq, RuntimeError())
					else:
						return True

		return False

	def add_asset_router(self, router: BaseAssetRouter) -> None:
		"""
		Adds a regular asset router to the asset router stack, which
		may influence loading behavior of regular assets.
		Invalidates the asset system manager's cache.
		"""
		self.asset_router_stack.append(router)
		for name, specs in router.get_library_specs().items():
			if name in self._library_specs:
				logger.warning(f"Router introduced already existing library {name!r}, ignoring.")
				continue
			self._library_specs[name] = specs
		self.clear_caches()

	def remove_asset_router(self, router: BaseAssetRouter) -> None:
		"""
		Removes an asset router and invalidates the cache.
		"""
		try:
			self.asset_router_stack.remove(router)
		except ValueError:
			return
		self.clear_caches()

	def _route_asset(
		self, path: str, asset_type_name: str, options: t.Dict[str, t.Any]
	) -> t.Tuple[str, t.Optional[t.Dict[str, t.Any]], t.List[PostLoadProcessor]]:
		"""
		Figures out an absolute path, and possibly overriding options
		or post-load processors for the given asset based on the asset
		system stack.
		If no routers had this asset, will use the
		``AssetSystemManager``'s own default directory to make the path
		absolute.
		"""
		post_load_processors = []
		additional_options = None
		for as_ in reversed(self.asset_router_stack):
			# TODO: Original options are always passed in. Not really relevant in use cases,
			# but maybe pass additional_options instead, merged with options?
			if (entry := as_.has_asset(path, asset_type_name, options)) is not None:
				terminal, path, n_options, plp = entry
				if n_options is not None:
					if additional_options is None:
						additional_options = n_options
					else:
						additional_options.update(n_options)

				if plp is not None:
					post_load_processors.append(plp)

				if terminal:
					return path, additional_options, post_load_processors

		return os.path.join(self._cwd, path), additional_options, post_load_processors

	def _route_complex_asset(
		self, name: str, options: t.Dict[str, t.Any]
	) -> t.Tuple[t.Optional[t.Dict[str, t.Any]], t.List[PostLoadProcessor]]:
		"""
		Possibly figures out differing args and/or kwargs and/or
		post-load processors for a complex asset based on the current
		asset system stack.
		"""
		post_load_processors = []
		additional_options = None
		for as_ in reversed(self.asset_router_stack):
			if (entry := as_.has_complex_asset(name, options)) is not None:
				terminal, n_opts, plp = entry
				if plp is not None:
					post_load_processors.append(plp)

				if n_opts is not None:
					if additional_options is None:
						additional_options = n_opts
					else:
						additional_options.update(n_opts)

				if terminal:
					return additional_options, post_load_processors

		return additional_options, post_load_processors

	def load_pyobj(self, ident: t.Hashable) -> t.Any:
		"""
		Loads a pyobject by its identifier. While other assets are
		loaded from file paths by loader functions, the pyobj asset
		directory so-to-speak is built by the asset systems
		exclusively.
		"""
		if ident in self._pyobj_cache:
			return self._pyobj_cache[ident]

		for as_ in reversed(self.asset_router_stack):
			have, o = as_.has_pyobj(ident)
			if have:
				self._pyobj_cache[ident] = o
				return o

		raise AssetNotFoundError(f"Could not find pyobj {ident!r} in current asset router stack!")

	def discover_libraries(self) -> None:
		self._resolved_libraries.clear()
		self._discover_libraries(self._library_specs.keys())
		logger.info(
			f"Discovered {len(self._resolved_libraries)} asset libraries. "
			f"{sum(len(w) for v in self._resolved_libraries.values() for w in v.values())} "
			f"items in total."
		)

	def _discover_libraries(self, names: t.Iterable[str]) -> None:
		request = {name: self._library_specs[name] for name in names}
		for as_ in reversed(self.asset_router_stack):
			result = as_.discover_libraries(request.copy())
			for disc_name, disc_items in result.items():
				request.pop(disc_name)
				self._resolved_libraries[disc_name] = disc_items

			if not request:
				return

		for undisc_name in request:
			logger.info(f"Library {undisc_name!r} fell off")
			self._resolved_libraries[undisc_name] = {}

	def load_library(self, name: str) -> t.Dict[str, t.Sequence[ParameterTuple]]:
		"""
		Returns a library's items.
		"""
		if name not in self._resolved_libraries:
			self._discover_libraries((name,))
			logger.info(
				f"Discovered library {name}. "
				f"{sum(len(w) for w in self._resolved_libraries[name].values())} items."
			)

		return self._resolved_libraries[name]

	def remove_asset_type(self, name: str) -> None:
		if name not in self.asset_type_registry:
			raise KeyError(f"Cannot remove unknown asset type {name}")
		self.asset_type_registry.pop(name)

	def _check_signature(self, sig: inspect.Signature) -> None:
		for param_name, param in sig.parameters.items():
			if param.kind is inspect.Parameter.POSITIONAL_ONLY:
				raise TypeError("No positional-only parameters in loaders, please")
			if param.kind is inspect.Parameter.VAR_POSITIONAL:
				raise TypeError("Cannot handle *args in loader.")

	def _register_asset_provider(
		self,
		asset_type_name: str,
		provider_cls: t.Type[BaseAssetProvider[T]],
		is_complex: bool,
		is_cache_aware: bool,
	) -> t.Callable[..., T]:
		# TODO: The is_complex and cache_aware vars do not change.
		# Untangle into copy-paste methods once this stuff is stable.

		if is_cache_aware > is_complex:
			raise ValueError("Cache aware asset providers must be complex")

		if asset_type_name in self.asset_type_registry:
			raise ValueError(f"Asset type of name {asset_type_name!r} already exists")

		provider = provider_cls(self)

		# Verify signature
		sig = inspect.signature(provider.load)
		self._check_signature(sig)
		if not is_complex:
			if "path" not in sig.parameters:
				raise TypeError(
					"SingleFileAssetProvider.load signatures must begin with the 'path' parameter"
				)
			if list(sig.parameters.values())[0].name != "path":
				raise TypeError("First parameter must be 'path' for a SingleFileAssetProvider")

		# Make signature without cache args, will help us later
		if is_cache_aware:
			sig_nocache = inspect.Signature(
				[p for n, p in sig.parameters.items() if n not in ("cache", "cache_key")],
				return_annotation = sig.return_annotation,
			)
		else:
			sig_nocache = sig

		# Mush loading steps into a regular and threaded loader function
		loading_steps = provider.get_loading_steps()
		if not loading_steps:
			raise ValueError("No loading steps!")

		if len(loading_steps) == 1:
			regular_loader_func = loading_steps[0][0]

			if loading_steps[0][1]:
				# Function suited for thread, just forward to it
				def threaded_loader_func(relay_queue: queue.Queue, *args, **kwargs):
					# sleep(0.1)  # fancy loading screen slowdown
					return regular_loader_func(*args, **kwargs)
			else:
				# Function not suited for thread, schedule and wait for it
				def augmented_loader(_, relay_queue: queue.Queue, *args, **kwargs):
					relay_queue.put(regular_loader_func(*args, **kwargs))

				def threaded_loader_func(relay_queue: queue.Queue, *args, **kwargs):
					# sleep(0.1)  # fancy loading screen slowdown
					self._clock.schedule_once(augmented_loader, 0.0, relay_queue, *args, **kwargs)
					return relay_queue.get()
		else:
			# Regular loader func simply chains all the loadsteps
			*inter_steps, last_step = loading_steps

			def regular_loader_func(*args, **kwargs):
				for f, _ in inter_steps:
					args, kwargs = f(*args, **kwargs)
				return last_step[0](*args, **kwargs)

			# Alternative approach
			# def make_chained(funcs):
			# 	if len(funcs) == 1:
			# 		return funcs[0]
			# 
			# 	i = -1
			# 	next_ = funcs[-1]
			# 	while -i < len(funcs):
			# 		i -= 1
			# 
			# 		def inner(p, n, *args, **kwargs):
			# 			new_args, new_kwargs = p(*args, **kwargs)
			# 			return n(*new_args, **new_kwargs)
			# 
			# 		next_ = functools.partial(inner, funcs[i], next_)
			# 
			# 	return next_
			# 
			# regular_loader_func = make_chained(loading_steps)

			# NOTE: Creates functions every call, but what can you do
			def threaded_loader_func(relay_queue: queue.Queue, *args, **kwargs):
				# sleep(0.1)  # fancy loading screen slowdown
				for f, thread_suited in inter_steps:
					if thread_suited:
						args, kwargs = f(*args, **kwargs)
					else:
						def relay_loader(_, relay_queue: queue.Queue, *args, **kwargs):
							# stime = perf_counter()
							relay_queue.put(f(*args, **kwargs))
							# print("relay loader stalled for", perf_counter() - stime, "s")
						self._clock.schedule_once(relay_loader, 0.0, relay_queue, *args, **kwargs)
						args, kwargs = relay_queue.get()

				if last_step[1]:
					return last_step[0](*args, **kwargs)
				else:
					def relay_loader(_, relay_queue: queue.Queue, *args, **kwargs):
						# stime = perf_counter()
						relay_queue.put(last_step[0](*args, **kwargs))
						# print("relay loader stalled for", perf_counter() - stime, "s")
					self._clock.schedule_once(relay_loader, 0.0, relay_queue, *args, **kwargs)
					return relay_queue.get()

		# Generate the ultimate loader func responsible for asset router resolving and
		# cache interaction
		@functools.wraps(provider.load)
		def gen_loader(*args, cache: bool = True, **kwargs) -> T:
			if is_cache_aware:
				ba = sig_nocache.bind(*args, **kwargs)
			else:
				ba = sig.bind(*args, **kwargs)
			ba.apply_defaults()

			if not is_complex:
				ba.arguments["path"] = path_to_string(ba.arguments["path"])

			cache_key = None
			if cache:
				if is_complex:
					cache_key = provider.create_cache_key(*args, **kwargs)
				else:
					# Use ba to get the modified path in there
					cache_key = provider.create_cache_key(*ba.args, **ba.kwargs)

				if (r := self._lookup_cache_key(asset_type_name, cache_key))[0]:
					# print(f"Cache hit on {asset_type_name}, {cache_key=}")
					return r[1]

				# If we're at this point, the asset will need to be loaded.

				self._threadloc.loading_stack.append([(asset_type_name, cache_key), []])
			else:
				self._threadloc.loading_stack.append("<uncached>")

			self._eviction_gate.wait()

			faked_kwargs = ba.arguments

			try:
				if is_complex:
					rp = None
					ro, rpr = self._route_complex_asset(asset_type_name, faked_kwargs)
				else:
					p = faked_kwargs.pop("path")
					rp, ro, rpr = self._route_asset(p, asset_type_name, faked_kwargs)

				if ro is not None:
					faked_kwargs.update(ro)

				if not is_complex:
					faked_kwargs["path"] = rp

				if is_cache_aware:
					if self._threadloc.threaded_load:
						load_result = threaded_loader_func(
							self._threadloc.relay_queue, cache, cache_key, **faked_kwargs
						)
					else:
						load_result = regular_loader_func(cache, cache_key, **faked_kwargs)
					asset = load_result.item
				else:
					if self._threadloc.threaded_load:
						asset = threaded_loader_func(self._threadloc.relay_queue, **faked_kwargs)
					else:
						asset = regular_loader_func(**faked_kwargs)
					load_result = LoadResult(asset, provider.get_estimated_asset_size(asset))

				for f in rpr:
					asset = f(asset)

				load_result.item = asset

				if cache:
					self._encache(asset_type_name, cache_key, load_result)

				# print(
				# 	("[T] " if self._threadloc.threaded_load else "") + ("[C] " if cache else "") +
				# 	asset_type_name +
				# 	f"; {cache_key}; {faked_kwargs}; {self._threadloc.loading_stack}"
				# )

			finally:
				self._threadloc.loading_stack.pop()

			return asset

		# Finally introduce asset type
		self.asset_type_registry[asset_type_name] = _AssetType(
			asset_type_name, is_complex, is_cache_aware, provider, gen_loader
		)

		return gen_loader

	def register_asset_provider(
		self,
		asset_type_name: str,
		provider_cls: t.Type[AssetProvider[T]], # ParamSpec retracted
	) -> t.Callable[..., T]:
		"""
		Registers the asset type `asset_type_name` with the
		AssetSystemManager.

		The provider must be a basic non-complex AssetProvider
		subclass exposing the ``load``, ``get_cache_key`` and possibly
		the ``get_estimated_asset_size`` methods.

		``load`` must turn an absolute path and possibly an amount of
		options into a concretely loaded asset.

		``get_cache_key`` must match ``load`` in its input signature
		and return a hashable that will be used to uniquely identify
		assets and access them from the asset cache.

		``get_estimated_asset_size`` may report a size, in bytes, for
		an object returned by this provider's ``load`` method.
		By default, it returns one. If otherwise not possible, return
		a rough estimate or one. This method may never return zero or
		negative values.

		Returns a loader function that can simply be used from your
		game's code like `load_image("assets/img/player.png")` or
		`load_sound("assets/snd/bg.ogg", stream=True, cache=False)`.
		"""
		assert issubclass(provider_cls, AssetProvider)

		return self._register_asset_provider(asset_type_name, provider_cls, False, False)

	def register_complex_asset_provider(
		self,
		asset_type_name: str,
		provider_cls: t.Type[AssetProvider[T]],
	) -> t.Callable[..., T]:
		"""
		Registers the complex asset type ``asset_type_name`` with
		the AssetSystemManager.

		These are more advanced than simple assets. They are not
		required to have a ``load`` signature starting with a
		``path`` and thus will not have this argument modified into
		an absolute path by the option routing process.

		These may load a number of other "atomic" assets and use them
		to construct more complex objects.
		"""
		assert issubclass(provider_cls, AssetProvider)

		return self._register_asset_provider(asset_type_name, provider_cls, True, False)

	def register_cache_aware_complex_asset_provider(
		self,
		asset_type_name: str,
		provider_cls: t.Type[BaseAssetProvider[T]], # ParamSpec retracted
	) -> t.Callable[..., T]:
		"""
		Registers a cache-aware asset type ``asset_type_name`` with
		the AssetSystemManager.

		This is the most complicated type of asset.

		``get_estimated_asset_size`` does not need to be implemented,
		as it will never be used.

		Their providers must expose the ``get_cache_usage``, ``unload``
		and ``get_loading_steps`` methods. Their load procedure may be
		scattered across multiple implementing methods, where methods
		are reported to be suitable for threaded loading or not via the
		boolean in the tuples returned by ``get_loading_steps``.
		Steps not suitable are guaranteed to be scheduled on the main
		thread via this ``AssetSystemManager``'s ``pyglet.Clock``.
		Useful and necessary for images and the like.

		The input signature for the first loading step will receive two
		extra arguments before what is passed into the loader:
		``cache`` (bool), and ``cache_key`` (Hashable), corresponding
		to whether the asset is chosen to be cached and its cache key.
		This complexity can be used to influence the loading behavior
		of assets.

		The steps have to communicate by returning 2-element tuples of
		args and kwargs which are then unpacked into the next step.

		Further, the load procedure may not return assets directly, but
		must wrap them in appropiate ``LoadResult`` objects.

		A cache-aware asset provider must implement ``unload``, which
		must free up any asset previously returned through its loading
		procedure. ``unload`` will receive the a key previously
		returned by the provider and the item to be unloaded as
		parameters.
		``unload`` will be called on the main thread. It also will be
		called while the asset system manager's cache lock is held,
		so should finish somewhat quickly.

		``get_cache_usage`` must return a two-element tuple which may
		hint at the provider's estimated memory usage; the first element
		being RAM usage, the second one VRAM usage.
		"""
		assert issubclass(provider_cls, CacheAwareAssetProvider)

		return self._register_asset_provider(asset_type_name, provider_cls, True, True)

	def shutdown(self) -> None:
		"""
		Cancels all threaded operations this `AssetSystemManager`
		is aware of and then stalls until they have completed.

		This should be called when exiting the game, otherwise there's
		a chance of worker threads waiting on queues that will never
		receive a response.

		Will not function properly if new ``LoadingProcedures`` are
		started while this is running. (Just don't do that™)
		"""
		with self.loading_procedure_management_lock:
			if not self._running_loading_procedures:
				return

			for p in self._running_loading_procedures:
				p.cancel()

		while self._running_loading_procedures or not self._eviction_process_state.completed:
			self._clock.call_scheduled_functions(self._clock.update_time())
			sleep(0.02)

	def clear_caches(self) -> None:
		"""
		Clears all of the asset system's caches.
		"""
		self._pyobj_cache.clear()
		self._resolved_libraries.clear()
		# TODO cache-aware providers are left out of this, fix later (TM)


_g_load_bytes = None
_g_load_text = None
_g_load_json = None
_g_load_xml = None
_g_load_sound = None
_g_load_image = None
_g_load_image_data = None
_g_load_frames = None

_g_load_pyobj = None

_asm = None


def initialize(clock: clock.Clock) -> AssetSystemManager:
	"""
	Initializes the asset system.
	Sets up the default loaders for bytes, text, json, xml, sound,
	images, frames and pyobj. Requires an OpenGL context to be active.
	"""
	global _asm, _g_load_bytes, _g_load_text, _g_load_json, _g_load_xml
	global _g_load_sound, _g_load_image, _g_load_image_data, _g_load_frames, _g_load_pyobj

	_asm = AssetSystemManager(clock)
	_g_load_bytes = _asm.register_asset_provider("bytes", BytesAssetProvider)
	_g_load_text = _asm.register_asset_provider("text", TextAssetProvider)
	_g_load_json = _asm.register_asset_provider("json", JSONAssetProvider)
	_g_load_xml = _asm.register_asset_provider("xml", XMLAssetProvider)
	_g_load_sound = _asm.register_asset_provider("sound", SoundAssetProvider)
	_g_load_image = _asm.register_cache_aware_complex_asset_provider("image", ImageAssetProvider)
	_g_load_image_data = _asm.register_asset_provider("image_data", ImageDataAssetProvider)
	_g_load_frames = _asm.register_complex_asset_provider("frames", FramesAssetProvider)

	_g_load_pyobj = _asm.load_pyobj

	return _asm

# Rewrap and redirect to singleton so stuff can be used via `load_image()` and
# not `self.game.assets.asset_type_registry["image"].loader()`.
# Typehints added manually cause current typecheckers can not handle this mess

def load_bytes(path: t.Union[str, Path], *, cache: bool = True) -> bytes:
	if _g_load_bytes is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_bytes(path, cache=cache)

def load_text(path: t.Union[str, Path], encoding: str = "utf-8", *, cache: bool = True) -> str:
	if _g_load_text is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_text(path, encoding, cache=cache)

def load_json(path: t.Union[str, Path], encoding: str = "utf-8", *, cache: bool = True) -> t.Dict:
	if _g_load_json is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_json(path, encoding, cache=cache)

def load_xml(path: t.Union[str, Path], *, cache: bool = True) -> ElementTree:
	if _g_load_xml is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_xml(path, cache=cache)

def load_sound(
	path: t.Union[str, Path],
	stream: bool = False,
	decoder: t.Optional["MediaDecoder"] = None,
	*,
	cache: bool = True,
) -> Source:
	if _g_load_sound is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_sound(path, stream, decoder, cache=cache)

def load_image(
	path: t.Union[str, Path], atlas_hint: t.Hashable = None, *, cache: bool = True
) -> Texture:
	if _g_load_image is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_image(path, atlas_hint, cache=cache)

def load_image_data(path: t.Union[str, Path], *, cache: bool = True) -> "ImageData":
	if _g_load_image_data is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_image_data(path, cache=cache)

def load_frames(path: t.Union[str, Path], *, cache: bool = True) -> FrameCollection:
	"""
	Loads animation frames from path.
	Will return a `FrameCollection`, which can directly be set to a
	sprite's `frames` attribute.
	"""
	if _g_load_frames is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_frames(path, cache=cache)

def load_pyobj(ident: t.Hashable) -> t.Any:
	if _g_load_pyobj is None:
		raise RuntimeError("Asset system not initialized!")
	return _g_load_pyobj(ident)
