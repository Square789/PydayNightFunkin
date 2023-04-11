"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from collections import defaultdict
import functools
import json
from pathlib import Path
import typing as t
from xml.etree.ElementTree import ElementTree

from loguru import logger
from pyglet import font
from pyglet import image
from pyglet.image import get_max_texture_size
from pyglet.image.atlas import TextureBin
from pyglet import media

from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser
from pyday_night_funkin.core import ogg_decoder

if t.TYPE_CHECKING:
	from pyglet.image import AbstractImage, Texture
	from pyglet.media.codecs import MediaDecoder


class AssetNotFoundError(KeyError):
	pass


class ResourceOptions:
	pass

# typing stuff begin
ResourceOptionsT = t.TypeVar("ResourceOptionsT", bound="ResourceOptions")
# P = t.ParamSpec("P") if hasattr(t, "ParamSpec") else None
T = t.TypeVar("T")
U = t.TypeVar("U")

PostLoadProcessor = t.Callable[[T], T]

# typing stuff end

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


class AssetRouterEntry:
	__slots__ = ("path", "options", "post_load_processor")

	def __init__(
		self,
		path: t.Optional[str] = None,
		options: t.Optional[ResourceOptions] = None,
		post_load_processor: t.Optional[PostLoadProcessor] = None,
	) -> None:
		self.path = path
		self.options = options
		self.post_load_processor = post_load_processor


class AssetRouter:
	def __init__(self, asset_map: t.Optional[t.Dict[str, AssetRouterEntry]]) -> None:
		self._asset_map = {} if asset_map is None else asset_map

	def has_asset(
		self, path: str, asset_type_name: str, options: t.Optional[ResourceOptions]
	) -> t.Optional[t.Tuple[str, t.Optional[ResourceOptions], t.Optional[PostLoadProcessor]]]:
		"""
		Determines whether an asset exists in this AssetRouter by its
		path.
		If the asset exists, a three-length tuple is returned. The
		tuple element at [0] will be the true path to it, [1] may be
		overridden options the asset should be loaded with or the
		original options if none were found and [2] may be an
		additional function that modifies the asset after loading.
		If the asset does not exist, leaves it alone returning `None`.

		This method can be overridden to also react to
		`asset_type_name` if you dare use such stringly-typed evils.
		"""
		if (entry := self._asset_map.get(path)) is not None:
			return (
				path if entry.path is None else entry.path,
				options if entry.options is None else entry.options,
				entry.post_load_processor,
			)

		return None

class ComplexAssetRouter:
	def has_asset(
		self, asset_type_name: str, *args: t.Any, **kwargs: t.Any
	) -> t.Optional[
		t.Tuple[t.Tuple[t.Any, ...], t.Dict[str, t.Any], t.Optional[PostLoadProcessor]
	]]:
		return None


class PyobjRouter:
	def __init__(self, pyobj_map: t.Dict[t.Hashable, t.Any]) -> None:
		self._pyobj_map = {} if pyobj_map is None else pyobj_map

	def has_pyobj(self, ident: t.Hashable) -> t.Tuple[bool, t.Any]:
		"""
		Returns a two-element tuple indicating whether this asset
		system knows an object with this name.
		If it does, [0] is True and [1] will be the object.
		If it does not, [0] is False and [1] irrelevant.
		"""
		if ident in self._pyobj_map:
			return (True, self._pyobj_map[ident])
		else:
			return (False, None)


class _AssetSystemManager:
	"""
	# TODO
	"""

	def __init__(self) -> None:
		self.asset_router_stack: t.List[AssetRouter] = []
		self.complex_asset_router_stack: t.List[ComplexAssetRouter] = []
		self.pyobj_router_stack: t.List[PyobjRouter] = []

		self.asset_type_registry: t.Set[str] = set()

		self.asset_dir = Path.cwd() / "assets"
		self._cache: t.Dict[str, t.Dict[t.Hashable, t.Any]] = {"image": {}}
		self._pyobj_cache: t.Dict[t.Hashable, t.Any] = {}

		self.tex_bin_size = min(4096, get_max_texture_size())
		make_tex_bin = lambda: TextureBin(self.tex_bin_size, self.tex_bin_size)
		self._hinted_tex_bin: t.Dict[t.Hashable, TextureBin] = defaultdict(make_tex_bin)
		self._tex_bin = make_tex_bin()

	def add_asset_router(self, router: AssetRouter) -> None:
		"""
		Adds a regular asset router to the asset router stack, which
		may influence loading behavior of regular assets.
		Invalidates the asset system manager's cache.
		"""
		self.asset_router_stack.append(router)
		self.clear_cache()

	def remove_asset_router(self, router: AssetRouter) -> None:
		"""
		Removes an asset router and invalidates the cache.
		"""
		try:
			self.asset_router_stack.remove(router)
		except ValueError:
			return
		self.clear_cache()

	def add_complex_asset_router(self, router: ComplexAssetRouter) -> None:
		"""
		Adds a complex asset router to the complex asset router stack
		which may influence the behavior of complex assets.
		Invalidates the asset system manager's cache.
		"""
		self.complex_asset_router_stack.append(router)
		self.clear_cache()

	def remove_complex_asset_router(self, router: ComplexAssetRouter) -> None:
		"""
		Removes a complex asset router and ivalidates the cache.
		"""
		try:
			self.complex_asset_router_stack.remove(router)
		except ValueError:
			return
		self.clear_cache()

	# TODO: pyobj routers are really just glorified dicts (ok this is python, everything is),
	# but i forgot why i have them in the first place. maybe reevaluate that.
	def add_pyobj_router(self, router: PyobjRouter) -> None:
		self.pyobj_router_stack.append(router)
		self._pyobj_cache.clear()

	def remove_pyobj_router(self, router: PyobjRouter) -> None:
		try:
			self.pyobj_router_stack.remove(router)
		except ValueError:
			return
		self._pyobj_cache.clear()

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
		should_store = img.width < self.tex_bin_size and img.height <= self.tex_bin_size
		if not should_store:
			return (img, False)

		try:
			return (target_bin.add(img), True)
		except Exception as e:
			logger.warning(f"Failed storing image {img} in atlas {atlas_hint}: {e}")
			return (img, False)

	def _get_full_path(self, tail: t.Union[Path, str]) -> str:
		return str(self.asset_dir / tail)

	def _process_asset(
		self, path: str, asset_type_name: str, options: t.Optional[ResourceOptions]
	) -> t.Tuple[str, t.Optional[ResourceOptions], t.Optional[PostLoadProcessor]]:
		"""
		Possibly figures out a different path, different options or a
		post-load processor for the given asset based on the asset
		system stack. Will always fall back to returning the input
		without a post-load processor if none applied.
		"""
		for as_ in reversed(self.asset_router_stack):
			if (entry := as_.has_asset(path, asset_type_name, options)) is not None:
				return entry

		return path, options, None

	def _process_complex_asset(
		self, name: str, *args: t.Any, **kwargs: t.Any
	) -> t.Tuple[t.Tuple[t.Any, ...], t.Dict[str, t.Any], t.Optional[PostLoadProcessor]]:
		"""
		Possibly figures out differing args and/or kwargs and/or a
		post-load processor for a complex asset based on the current
		asset system stack.
		"""
		for as_ in reversed(self.complex_asset_router_stack):
			if (entry := as_.has_asset(name, *args, **kwargs)) is not None:
				return entry

		return (args, kwargs, None)

	def load_pyobj(self, ident: t.Hashable) -> t.Any:
		"""
		Loads a pyobject by its identifier. While other assets are
		loaded from file paths by loader functions, the pyobj asset
		directory so-to-speak is built by the asset systems
		exclusively.
		"""
		if ident in self._pyobj_cache:
			return self._pyobj_cache[ident]

		for as_ in reversed(self.pyobj_router_stack):
			have, o = as_.has_pyobj(ident)
			if have:
				self._pyobj_cache[ident] = o
				return o

		raise AssetNotFoundError(f"Could not find {ident!r} in current pyobj router stack!")

	def load_image(
		self, path: str, cache: bool = True, options: t.Optional[ImageResourceOptions] = None
	) -> "Texture":
		img_cache = self._cache["image"]
		in_opt = ImageResourceOptions() if options is None else options
		cache_key = (path, in_opt)
		if cache_key in img_cache:
			return img_cache[cache_key]

		true_path_tail, true_opt, post_load_processor = self._process_asset(
			path, "image", in_opt
		)
		if not isinstance(true_opt, ImageResourceOptions):
			raise RuntimeError("Asset system delivered incompatible options for asset.")

		data = image.load(self._get_full_path(true_path_tail))
		if post_load_processor is not None:
			data = post_load_processor(data)
		data = self.store_image(data, true_opt.atlas_hint)[0].get_texture()

		if cache:
			img_cache[cache_key] = data

		return data

	def _check_and_make_asset_type_cache(self, name: str) -> t.Dict:
		if name in self.asset_type_registry:
			raise ValueError(f"Asset of name {name} already exists")
		self._cache[name] = {}
		return self._cache[name]

	def remove_asset_type(self, name: str) -> None:
		if name not in self.asset_type_registry:
			raise KeyError(f"Cannot remove unknown asset type {name}")
		self.asset_type_registry.remove(name)
		self._cache.pop(name)

	def register_optionless_asset_type(
		self, name: str, loader_function: t.Callable[[str], T]
	):
		"""
		Registers an optionless asset type of name `name` with the
		AssetSystemManager.
		"""
		cache_dict = self._check_and_make_asset_type_cache(name)

		@functools.wraps(loader_function)
		def gen_optionless_loader(path: str, cache: bool = True) -> T:
			if path in cache_dict:
				return cache_dict[path]

			true_path_tail, _, post_load_processor_func = self._process_asset(path, name, None)
			data = loader_function(self._get_full_path(true_path_tail))
			if post_load_processor_func is not None:
				data = post_load_processor_func(data)
			if cache:
				cache_dict[path] = data

			return data

		self.asset_type_registry.add(name)
		return gen_optionless_loader

	def register_asset_type(
		self,
		name: str,
		loader_function: t.Callable[[str, ResourceOptionsT], T],
		options_factory: t.Callable[[], ResourceOptionsT],
		options_validator: t.Optional[t.Callable[[t.Any], t.Union[str, bool]]] = None,
	):
		"""
		Registers the asset type `name` with the AssetSystemManager.
		`loader_function` must turn a path and a specifically created
		for this asset `ResourceOptions` subclass instance into a
		concretely loaded asset.

		`options_factory` must supply default options to the loader
		function. In most cases, the type name of the custom
		`ResourceOptions` should suffice.

		The asset system stack might override any default and passed
		in options. If that is expected, the `options_validator` can be
		given as an extra sanity check to check the validity of options
		given by the asset system stack. This function must return
		`True` if the argument is valid, and may return anything else
		to indicate failure. A string can be given as an explicit
		reason for failure.

		Returns a loader function that can simply be used from your
		game's code like `load_image("assets/img/player.png")` or
		`load_sound("assets/snd/bg.ogg", options=None, cache=False)`.
		"""
		cache_dict = self._check_and_make_asset_type_cache(name)

		@functools.wraps(loader_function)
		def gen_loader(
			path: str,
			options: t.Optional[ResourceOptionsT] = None,
			cache: bool = True,
		) -> T:
			options = options_factory() if options is None else options
			cache_key = (path, options)
			if cache_key in cache_dict:
				return cache_dict[cache_key]

			true_path_tail, true_options, post_load_processor_func = self._process_asset(
				path, name, options
			)
			if true_options is not options and options_validator is not None:
				ovres = options_validator(true_options)
				if ovres is not True:
					raise RuntimeError(
						f"Options validator for asset type {name} disagreed with options "
						f"returned by an asset system{': ' + str(ovres) if ovres else ''}."
					)

			data = loader_function(self._get_full_path(true_path_tail), true_options)
			if post_load_processor_func is not None:
				data = post_load_processor_func(data)
			if cache:
				cache_dict[cache_key] = data
			return data

		self.asset_type_registry.add(name)
		return gen_loader

	# typing on this kinda sucks and is post-3.8 anyways;
	# can't figure out nicer stuff rn, maybe a generic protocol?
	# def register_complex_asset_type(
	# 	self,
	# 	name: str,
	# 	cache_key_maker: "t.Callable[P, t.Hashable]",
	# 	loader_func: "t.Callable[P, T]",
	# ) -> "t.Callable[t.Concatenate[P.args, bool, P.kwargs, P], T]":
	def register_complex_asset_type(
		self,
		name: str,
		cache_key_maker: t.Callable[..., t.Hashable],
		loader_func: t.Callable[..., T],
	):
		"""
		Registers the complex asset type `name` with the
		AssetSystemManager.
		These:
		 - Completely ignore the asset system stack due to their
		   disconnect from paths.
		 - Largely leave proper behavior up to the user/the
		   `loader_func` you pass in.
		 - Can take any amount of arguments
		 - Do not use options apart from what the passed in arbitrary
		   arguments mean to them. `cache_key_maker` is expected to
		   create a proper cache key for distinct arguments.

		It is recommended that the `loader_func` loads other "atomic"
		assets without caching and places them in a tuple or other kind
		of collection that holds references to them. This way, on
		caching the collection will be placed in the ASM and all
		resources removed again when the cache entry is removed.

		NOTE: The argument count indetermination makes `cache` in
		the generated loader function a kwarg-only argument.
		"""
		cache_dict = self._check_and_make_asset_type_cache(name)

		@functools.wraps(loader_func)
		def gen_complex_loader(*args: t.Any, cache: bool = True, **kwargs: t.Any) -> T:
			cache_key = cache_key_maker(*args, **kwargs)
			if cache_key in cache_dict:
				return cache_dict[cache_key]

			prc_args, prc_kwargs, post_load_processor = self._process_complex_asset(
				name, *args, **kwargs
			)
			data = loader_func(*prc_args, **prc_kwargs)
			if post_load_processor is not None:
				data = post_load_processor(data)
			if cache:
				cache_dict[cache_key] = data

			return data

		self.asset_type_registry.add(name)
		return gen_complex_loader

	def clear_cache(self) -> None:
		"""
		Clears the asset system's cache.
		"""
		self._pyobj_cache.clear()
		# print("PURGING CACHE")
		for d in self._cache.values():
			d.clear()


_asm = _AssetSystemManager()

def _load_bytes_plain(path: str) -> bytes:
	with open(path, "rb") as f:
		return f.read()
load_bytes = _asm.register_optionless_asset_type("bytes", _load_bytes_plain)

def _load_text_plain(path: str, options: TextResourceOptions) -> str:
	with open(path, "r", encoding=options.encoding) as f:
		return f.read()
load_text = _asm.register_asset_type("text", _load_text_plain, TextResourceOptions)

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
load_image = _asm.load_image

add_asset_router = _asm.add_asset_router
add_complex_asset_router = _asm.add_complex_asset_router
add_pyobj_router = _asm.add_pyobj_router
remove_asset_router = _asm.add_asset_router
remove_complex_asset_router = _asm.add_complex_asset_router
remove_pyobj_router = _asm.add_pyobj_router
invalidate_cache = _asm.clear_cache
register_asset_type = _asm.register_asset_type
register_optionless_asset_type = _asm.register_optionless_asset_type
register_complex_asset_type = _asm.register_complex_asset_type
