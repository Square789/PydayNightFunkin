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
import fnmatch
import functools
import glob
import inspect
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import typing as t
from xml.etree.ElementTree import ElementTree

from loguru import logger
from pyglet import clock
from pyglet import image
from pyglet.image import AbstractImage, Texture
from pyglet.image.atlas import TextureBin
from pyglet.math import Vec2
from pyglet import media
from pyglet.media.codecs.base import Source, StaticSource

from pyday_night_funkin.core.animation import FrameCollection
from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser
from pyday_night_funkin.core import ogg_decoder

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


def _path_to_string(path: t.Union[str, Path]) -> str:
	return path if isinstance(path, str) else str(path)


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
		self._dir = _path_to_string(asset_directory)

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
		path = _path_to_string(options["path"])

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


class CacheEntry(t.Generic[T]):
	"""An cache entry for an asset."""

	def __init__(self, item: T) -> None:
		self.item = item
		self.last_requested = 0
		self.hits = 0
		self.estimated_size_system = 0
		self.estimated_size_gpu = 0


class Cache(t.Generic[T]):
	"""A cache for assets of a certain type."""

	def __init__(self) -> None:
		self._dict: t.Dict[t.Hashable, CacheEntry[T]] = {}
		self._estimated_memory_usage = 0

	def get_memory_usage(self) -> int:
		return self._estimated_memory_usage

	def add(self, key: t.Hashable, item: T, *_a, **_k) -> T:  # P.args/kwargs retracted
		if key in self._dict:
			raise ValueError(f"Cache entry for {key!r} exists already")
		self._dict[key] = CacheEntry(item)
		self._estimated_memory_usage += self._get_size_of(item)
		return item

	def pass_by(self, item: T, *_a, **_k) -> T:  # P.args/kwargs retracted
		return item

	def _get_size_of(self, item: T) -> int:
		return sys.getsizeof(item)

	def get(self, key: t.Hashable) -> t.Tuple[bool, t.Optional[T]]:
		if key in self._dict:
			return (True, self._dict[key].item)
		return (False, None)

	def clear(self) -> None:
		self._dict.clear()
		self._estimated_memory_usage = 0


class LoadResult(t.Generic[T]):
	__slots__ = ("item", "estimated_size_system", "estimated_size_gpu")

	def __init__(self, item: T, estimated_size_system = 0, estimated_size_gpu = 0) -> None:
		self.item = item
		self.estimated_size_system = estimated_size_system
		self.estimated_size_gpu = estimated_size_gpu


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
		return 0

	@t.final
	def get_cache_usage(self) -> t.Tuple[int, int]:
		return (0, 0)

	@t.final
	def get_loading_steps(self) -> t.Tuple[t.Tuple[t.Callable, bool]]:
		return ((self.load, True),)

	@abc.abstractmethod
	def load(self, path: str, *_a, **_k) -> T:
		raise NotImplementedError()

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
			return len(item)


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
			return len(item)


def _recursive_size_of(item: object) -> int:
	if isinstance(item, dict):
		return (
			sum(_recursive_size_of(k) + _recursive_size_of(v) for k, v in item.items()) +
			sys.getsizeof(item)
		)
	elif isinstance(item, list):
		return sum(_recursive_size_of(i) for i in item) + sys.getsizeof(item)
	return sys.getsizeof(item)


class JSONAssetProvider(AssetProvider[t.Dict]):
	def load(self, path: str, encoding: str = "utf-8") -> str:
		with open(path, "r", encoding=encoding) as f:
			return json.load(f)

	def create_cache_key(self, path: str, encoding: str = "utf-8") -> t.Hashable:
		return (path, encoding)

	def get_estimated_asset_size(self, item: t.Dict) -> int:
		try:
			return _recursive_size_of(item)
		except TypeError:
			return 0


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
			return 0


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
		return 0


class ImageDataAssetProvider(AssetProvider["ImageData"]):
	def load(self, path: str) -> "ImageData":
		return image.load(path)

	def create_cache_key(self, path: str) -> t.Hashable:
		return path

	def get_estimated_asset_size(self, item: "ImageData") -> int:
		size = sys.getsizeof(item, 0)
		if isinstance(item._current_data, bytes):
			try:
				size += sys.getsizeof(item._current_data)
			except TypeError:
				size += len(item._current_data)
		return size


class ImageAssetProvider(CacheAwareAssetProvider[Texture]):
	def __init__(self, asm: "AssetSystemManager") -> None:
		super().__init__(asm)

		self.tex_bin_size = 4096
		make_tex_bin = lambda: TextureBin(self.tex_bin_size, self.tex_bin_size)
		self._hinted_tex_bins: t.Dict[t.Hashable, TextureBin] = defaultdict(make_tex_bin)
		self._tex_bin = make_tex_bin()

		self._texture_cache_size = 0

	def get_loading_steps(self) -> t.Tuple[t.Tuple[t.Callable, bool], ...]:
		return ((self.load, True), (self.load_create_texture, False))

	def load(
		self,
		cache: bool,
		cache_key: t.Hashable,
		path: str,
		atlas_hint: t.Hashable = None,
	):
		# NOTE: Not really worth it due to private access, but possibly saves work
		# that would otherwise be done in the main thread.
		# data_format = image_data.format
		# fmt, _ = image_data._get_gl_format_and_type(data_format)
		# if fmt is None:
		# 	data_format = {1: 'R', 2: 'RG', 3: 'RGB', 4: 'RGBA'}.get(len(data_format))
		# image_data._convert(data_format, abs(image_data._current_pitch))

		return (load_image_data(path, cache=False), cache, cache_key, atlas_hint), {}

	def get_cache_usage(self) -> t.Tuple[int, int]:
		return (0, self._texture_cache_size)

	def load_create_texture(
		self,
		img_data: "ImageData",
		cache: bool,
		cache_key: t.Hashable,
		atlas_hint: t.Hashable,
	) -> LoadResult[Texture]:
		unbinned_size = 0
		texture = None

		if cache and img_data.width <= self.tex_bin_size and img_data.height <= self.tex_bin_size:
			target_bin = (
				self._tex_bin if atlas_hint is None else
				self._hinted_tex_bins[atlas_hint]
			)
			try:
				texture = target_bin.add(img_data)
			except Exception as e:
				logger.warning(f"Failed storing image {img_data} in atlas {atlas_hint}: {e}")
			else:
				self._texture_cache_size = 0
				for bin in (self._tex_bin, *self._hinted_tex_bins.values()):
					for atlas in bin.atlases:
						# Textures are rather hardwired to use RGBA8
						self._texture_cache_size += atlas.texture.width * atlas.texture.height * 4

		if texture is None:
			unbinned_size = img_data.width * img_data.height * 4
			texture = img_data.get_texture()

		return LoadResult(texture, 0, unbinned_size)

	def create_cache_key(self, path: str, atlas_hint: t.Hashable = None) -> t.Hashable:
		# NOTE: Really ugly, but complex assets need to ensure this
		return _path_to_string(path)


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


class AssetType(t.Generic[T]):
	def __init__(self, name: str, is_complex: bool, is_cache_aware: bool) -> None:
		self.name = name
		self.is_complex = is_complex
		self.is_cache_aware = is_cache_aware
		self.cache: t.Optional[Cache] = None
		self.provider: t.Optional[BaseAssetProvider[T]] = None
		self.loader: t.Optional[t.Callable[..., T]] = None
		self.current_provider_cache_memory_usage_system = 0
		self.current_provider_cache_memory_usage_gpu = 0


class CacheStats:
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
	def __init__(
		self,
		args: t.Optional[t.Tuple[t.Any, ...]] = None,
		kwargs: t.Optional[t.Dict[str, t.Any]] = None,
		completion_tag: t.Optional[str] = None,
	) -> None:
		self._args = () if args is None else args
		self._kwargs = {} if kwargs is None else kwargs

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
		self.args = base_request._args
		self.kwargs = base_request._kwargs
		self.completion_tag = base_request.completion_tag
		self.completion_tag_idx = base_request.completion_tag_idx


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

		self._lock = threading.RLock()
		# Some notes on this lock:
		# It needs to be an RLock in the event that a few `on_done_callback`s run
		# immediately
		# It is sometimes intentionally not taken when checking for `_cancelled`

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
			self._cancelled = True
			for f in self._asset_requests.values():
				if not f.future.cancel():
					# Future failed cancelling, meaning it's either done or running.
					# We cannot add check logic in `_asset_available` or `_library_available`,
					# as a finished callback won't call those anymore and it's impossible to safely
					# determine whether it's running or not by making another call here (Without
					# copy-pasting internals and grabbing the future's `_condition` yourself).
					# So, just tack on another callback, which will run in both cases,
					# decrementing the counter immediately or later.
					self._cancelled_pending_return += 1
					f.future.add_done_callback(self._on_cancellation_doorstopper_done)
			for f in self._library_requests.values():
				if not f.future.cancel():
					self._cancelled_pending_return += 1
					f.future.add_done_callback(self._on_cancellation_doorstopper_done)
			self._executor.shutdown(wait=False)

	def _on_cancellation_doorstopper_done(self, future: Future) -> None:
		with self._lock:
			self._cancelled_pending_return -= 1

	def _submit_asset_loading_job(self, asset_request: _ProcessedAssetRequest, f, *args, **kwargs) -> t.Optional[Future]:
		with self._lock:
			if self._cancelled:
				# I guess we could get rid of none checks by introducing some kind of dummy
				# "always cancelled" future, but that's be really ugly, so no
				return None

			future = self._executor.submit(f, *args, **kwargs)
			self._asset_requests[asset_request].future = future
			return future

	def _submit_library_loading_job(self, library_name: str, f, *args, **kwargs) -> t.Optional[Future]:
		with self._lock:
			if self._cancelled:
				return None

			future = self._executor.submit(f, *args, **kwargs)
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
				logger.warning("LoadingProcedure finality violated")

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

		# Finality can be guaranteed once there's no more pending completion callbacks
		# and all the libraries have been loaded
		# Kindof relies on the logic of the AssetSystemManager, but that's fine
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

			comp_tag = asset_request.completion_tag
			if comp_tag is None:
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

	def _library_available(self, lib_name: str, lib_request: LoadingRequest) -> None:
		"""
		A library previously returned through ``_get_new_library_requests``
		has been resolved and is now available.
		"""
		with self._lock:
			self._library_requests[lib_name].loaded = True
			self._last_loaded_asset = f"lib:{lib_name}"
			self._add_more_requests((lib_request,))

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


class AssetSystemManager:
	"""
	# TODO
	"""

	def __init__(self, pyglet_clock: clock.Clock) -> None:
		self._clock = pyglet_clock
		self.asset_router_stack: t.List[BaseAssetRouter] = []
		self.asset_type_registry: t.Dict[str, AssetType] = {}
		self._pyobj_cache: t.Dict[t.Hashable, t.Any] = {}
		self._cwd = Path.cwd()
		self.age = 0
		self._memory_usage_stats = CacheStats()
		self._cache_lock = threading.Lock()

		self._resolved_libraries: t.Dict[str, t.Dict[str, t.Sequence[ParameterTuple]]] = {}
		self._library_specs: t.Dict[str, t.Tuple[LibrarySpecPattern, ...]] = {}

		self._threadloc = threading.local()
		"""
		Thread-local data. Contains:
			`loading_stack`: Aids in tracking of dependent assets.

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

	def _lookup_cache_key(self, asset_type_name: str, key: t.Hashable) -> t.Any:
		return self.asset_type_registry[asset_type_name].cache.get(key)

	def _encache(self, asset_type_name: str, key: t.Hashable, value: LoadResult) -> None:
		asset_type = self.asset_type_registry[asset_type_name]

		asset_type.cache.add(key, value.item)
		pcs, pcg = asset_type.provider.get_cache_usage()
		self._memory_usage_stats.object_count += 1
		self._memory_usage_stats.system_memory_used += (
			value.estimated_size_system +
			(pcs - asset_type.current_provider_cache_memory_usage_system)
		)
		self._memory_usage_stats.gpu_memory_used += (
			value.estimated_size_gpu +
			(pcg - asset_type.current_provider_cache_memory_usage_gpu)
		)

		asset_type.current_provider_cache_memory_usage_system = pcs
		asset_type.current_provider_cache_memory_usage_gpu = pcg

		# ce = CacheEntry(value)
		# ce.last_requested = self.age
		# ce.estimated_size_system = value.estimated_size_system
		# ce.estimated_size_gpu = value.estimated_size_gpu

	def _remove_from_cache(self, asset_type_name: str, key: t.Hashable) -> None:
		pass

	def advance_age(self) -> None:
		"""
		Advances the age of the AssetSystemManager. This should be called at
		points where the underlying program undergoes a significant change in
		loaded assets, such as leaving a gameworld in favor of another with
		wildly different assets. This aids in considerations for which assets
		to unload.
		"""
		self.age += 1

	def start_threaded_load(self, request: LoadingRequest) -> LoadingProcedure:
		"""
		Start loading a multitude of items.

		By the end of it, all specified items will be in the cache and should be
		available quickly via their respective ``load`` methods.

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
		# 4 threads max since they're all still pretty likely to run a good amount of
		# python bytecode in the generated loader methods.
		# Don't want them to starve the main or media thread too much.
		executor = ThreadPoolExecutor(4, "AssetLoader", _tinit)

		lproc = LoadingProcedure(executor, self, request)

		self._drain_loading_procedure(lproc)

		return lproc

	def _drain_loading_procedure(self, lproc: LoadingProcedure) -> None:
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

	def _start_threaded_asset_request_load(
		self,
		lproc: LoadingProcedure,
		asset_request: _ProcessedAssetRequest,
	) -> None:
		args = asset_request.args
		kwargs = asset_request.kwargs

		asset_type = self.asset_type_registry[asset_request.asset_type_name]

		# Prevents the future running finishing callbacks before the request is aware of them, or
		# Or any bad race conds involving cancellation
		future = lproc._submit_asset_loading_job(asset_request, asset_type.loader, *args, **kwargs)
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
		if (exc := future.exception()) is not None:
			# TODO: Failure will cause the loading procedure to never finish,
			# figure this out
			logger.error(f"Threaded asset load: {exc}")
			return

		if future.cancelled():
			# Twitter got to us, no asset available, return
			return

		lproc._asset_available(asset_request, future.result())
		self._drain_loading_procedure(lproc)

	def _start_threaded_library_load(self, lproc: LoadingProcedure, library_name: str) -> None:
		future = lproc._submit_library_loading_job(library_name, self.load_library, library_name)
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
		if (exc := future.exception()) is not None:
			logger.error(f"Threaded library load: {exc}")
			return

		if future.cancelled():
			return

		lproc._library_available(lib_name, self._libraries_to_subrequest((lib_name,)))
		self._drain_loading_procedure(lproc)

	def _asset_request_check_cache(self, request: _ProcessedAssetRequest) -> t.Tuple[bool, t.Any]:
		asset_type = self.asset_type_registry[request.asset_type_name]

		# This `path` stringification is the worst
		args = request.args
		kwargs = request.kwargs
		if not asset_type.is_complex:
			if "path" in request.kwargs:
				kwargs = request.kwargs.copy()
				kwargs["path"] = _path_to_string(kwargs["path"])
			else:
				if len(args) >= 1:  # Otherwise invalid probably
					args = (_path_to_string(args[0]),) + args[1:]

		return asset_type.cache.get(asset_type.provider.create_cache_key(*args, **kwargs))

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
		Returns whether a LoadingRequest needs to make calls to load
		assets, so if any of its requested assets/libraries or and of
		its subrequest's assets/libraries are not cached.
		"""
		request = loading_request.copy()

		fake_proc = LoadingProcedure(None, self, request)

		did_something = True
		while did_something:
			did_something = False

			new_libs = fake_proc._get_new_libraries()
			for lib_name in new_libs:
				if lib_name in self._resolved_libraries:
					did_something = True
					fake_proc._library_available(lib_name, self._libraries_to_subrequest((lib_name,)))
				else:
					return True

			new_areqs = fake_proc._get_new_asset_requests()
			for areq in new_areqs:
				ck = self._asset_request_check_cache(areq)
				if ck[0]:
					did_something = True
					fake_proc._asset_available(areq, ck[1])
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

	def _check_and_add_asset_type(
		self,
		at: AssetType,
		provider_cls: t.Type[BaseAssetProviderT],
	) -> BaseAssetProviderT:
		if at.name in self.asset_type_registry:
			raise ValueError(f"Asset of name {at.name} already exists")

		provider = provider_cls(self)

		self.asset_type_registry[at.name] = at
		at.cache = Cache()
		at.provider = provider

		return provider

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
		cache_aware: bool,
	) -> t.Callable[..., T]:
		# TODO: The is_complex and cache_aware vars do not change.
		# Untangle into copy-paste methods once this stuff is stable.

		assert cache_aware <= is_complex

		at = AssetType(asset_type_name, is_complex, cache_aware)
		provider = self._check_and_add_asset_type(at, provider_cls)

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
		if cache_aware:
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
					# __import__("time").sleep(0.1)  # fancy loading screen slowdown
					return regular_loader_func(*args, **kwargs)
			else:
				# Function not suited for thread, schedule and wait for it
				def augmented_loader(_, relay_queue: queue.Queue, *args, **kwargs):
					relay_queue.put(regular_loader_func(*args, **kwargs))

				def threaded_loader_func(relay_queue: queue.Queue, *args, **kwargs):
					# __import__("time").sleep(0.1)  # fancy loading screen slowdown
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
				# __import__("time").sleep(0.1)  # fancy loading screen slowdown
				for f, thread_suited in inter_steps:
					if thread_suited:
						args, kwargs = f(*args, **kwargs)
					else:
						def relay_loader(_, relay_queue: queue.Queue, *args, **kwargs):
							# stime = __import__("time").perf_counter()
							relay_queue.put(f(*args, **kwargs))
							# print("relay loader stalled for", __import__("time").perf_counter() - stime, "s")
						self._clock.schedule_once(relay_loader, 0.0, relay_queue, *args, **kwargs)
						args, kwargs = relay_queue.get()

				if last_step[1]:
					return last_step[0](*args, **kwargs)
				else:
					def relay_loader(_, relay_queue: queue.Queue, *args, **kwargs):
						# stime = __import__("time").perf_counter()
						relay_queue.put(last_step[0](*args, **kwargs))
						# print("relay loader stalled for", __import__("time").perf_counter() - stime, "s")
					self._clock.schedule_once(relay_loader, 0.0, relay_queue, *args, **kwargs)
					return relay_queue.get()

		# Generate the ultimate loader func responsible for asset router resolving and
		# cache interaction
		@functools.wraps(provider.load)
		def gen_loader(*args, cache: bool = True, **kwargs) -> T:
			if cache_aware:
				ba = sig_nocache.bind(*args, **kwargs)
			else:
				ba = sig.bind(*args, **kwargs)
			ba.apply_defaults()

			if not is_complex:
				ba.arguments["path"] = _path_to_string(ba.arguments["path"])

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

			faked_kwargs = ba.arguments

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

			if cache_aware:
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
			# 	("[T] " if self._threadloc.threaded_load else "") + "loaded " +
			# 	("and encached " * cache) + asset_type_name + f"; {cache_key}; {faked_kwargs}"
			# )

			return asset

		# Don't forget to make the loader known here
		self.asset_type_registry[asset_type_name].loader = gen_loader

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
		By default, or if this is not possible, it should just return
		zero.

		Returns a loader function that can simply be used from your
		game's code like `load_image("assets/img/player.png")` or
		`load_sound("assets/snd/bg.ogg", options=None, cache=False)`.
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

		Their providers must expose the ``get_cache_usage`` and
		``get_loading_steps`` methods. Their load procedure may be
		scattered across multiple implementing methods, where methods
		are reported to be suitable for threaded loading or not via the
		boolean in the tuples returned by ``get_loading_steps``.
		Steps not suitable are guaranteed to be scheduled on the main
		thread via ``pyglet.clock.schedule_once``. Useful for images and
		the like.

		The input signature for the first loading step will receive two
		extra arguments before what is passed into the loader:
		``cache`` (bool), and ``cache_key`` (Hashable), corresponding
		to whether the asset is chosen to be cached and its cache key.
		This complexity can be used to influence the loading behavior
		of assets.

		# TODO there is no way to remove elements from cache, as there
		# is no way of clearing the asset cache in general, do that
		# for 0.0.53

		The steps have to communicate by returning 2-element tuples of
		args and kwargs which are then unpacked into the next step.

		Further, the load procedure may not return assets directly, but
		must wrap them in appropiate ``LoadResult`` objects.

		``get_cache_usage`` must return a two-element tuple which may
		hint at the provider's estimated memory usage; the first element
		being RAM usage, the second one VRAM usage.
		"""
		assert issubclass(provider_cls, CacheAwareAssetProvider)

		return self._register_asset_provider(asset_type_name, provider_cls, True, True)

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
