"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from collections import defaultdict
import json
from pathlib import Path
import typing as t
from xml.etree.ElementTree import ElementTree

from pyglet import image
from pyglet.image.atlas import AllocatorException, TextureBin
from pyglet import media

from pyday_night_funkin.constants import ADDRESS_PADDING
from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser
from pyday_night_funkin.core import ogg_decoder

if t.TYPE_CHECKING:
	from pyglet.image import AbstractImage, Texture


class AssetNotFoundError(ValueError):
	pass


class RouterNotFoundError(ValueError):
	pass


class Resource:
	"""
	A resource simply represents a relative file location on disk.
	They are compared and hashed by the path they point to.
	Resource subclasses implement a `load` method that loads data from
	disk based on the path and - potentially - options that are set
	on the resource at initialization.

	NOTE: When adding options to a resource that change the retrieved
	data in any way, do not forget to add these options to the
	subclass's `__eq__` and `__hash__` methods, otherwise the
	AssetSystemManager cache may return bad data.
	"""

	def __init__(self, path: t.Union[str, Path]) -> None:
		"""
		Creates a resource to be found at the given path.
		"""
		self.path = Path(path)

	def get_full_path(self, asm: "_AssetSystemManager") -> Path:
		"""
		Returns a path that is the concatted path of the given
		asset system manager's absolute root asset directory and this
		resource's path.
		"""
		return asm.asset_dir / self.path

	def load(self, asm: "_AssetSystemManager") -> t.Any:
		raise NotImplementedError("Implement this in a subclass!")

	def __eq__(self, o: object) -> bool:
		if isinstance(o, Resource):
			return self.path.resolve() == o.path.resolve()
		return NotImplemented

	def __hash__(self) -> int:
		return hash(str(self.path.resolve()))

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} {self.path!r} at "
			f"0x{id(self):0>{ADDRESS_PADDING}X}>"
		)


class PathResource(Resource):
	def load(self, asm: "_AssetSystemManager") -> Path:
		return self.get_full_path(asm)


class JSONResource(Resource):
	def load(self, asm: "_AssetSystemManager") -> t.Dict:
		with open(self.get_full_path(asm), "r") as f:
			return json.load(f)


class XMLResource(Resource):
	def load(self, asm: "_AssetSystemManager") -> ElementTree:
		et = ElementTree()
		with open(self.get_full_path(asm), "r", encoding="utf-8") as fp:
			et.parse(fp, AlmostXMLParser())
		return et


class ImageResource(Resource):
	def __init__(
		self,
		path: t.Union[str, Path],
		atlas_hint: t.Optional[t.Hashable] = None,
	) -> None:
		super().__init__(path)
		self.atlas_hint = atlas_hint

	def load(self, asm: "_AssetSystemManager") -> "Texture":
		return asm.store_image(
			image.load(self.get_full_path(asm)), self.atlas_hint
		)[0].get_texture()

	def __hash__(self) -> int:
		return hash((str(self.path.resolve()), self.atlas_hint))

	def __eq__(self, o: object) -> bool:
		if isinstance(o, ImageResource):
			return self.atlas_hint == o.atlas_hint and self.path.resolve() == o.path.resolve()
		return NotImplemented


class TextResource(Resource):
	def __init__(self, path: t.Union[str, Path], encoding: str = "utf-8",) -> None:
		super().__init__(path)
		self.encoding = encoding

	def load(self, asm: "_AssetSystemManager") -> str:
		with open(self.get_full_path(asm), encoding=self.encoding) as f:
			return f.read()

	def __hash__(self) -> int:
		return hash((str(self.path.resolve()), self.encoding))

	def __eq__(self, o: object) -> bool:
		if isinstance(o, TextResource):
			return self.encoding == o.encoding and self.path.resolve() == o.path.resolve()
		return NotImplemented


class OggResource(Resource):
	_decoder = ogg_decoder.get_decoders()[0]

	def __init__(self, path: t.Union[str, Path], stream: bool = False) -> None:
		super().__init__(path)
		self.stream = stream

	def load(self, asm: "_AssetSystemManager") -> media.Source:
		return media.load(
			str(self.get_full_path(asm)),
			streaming = self.stream,
			decoder = self._decoder,
		)

	def __hash__(self) -> int:
		return hash((str(self.path.resolve()), self.stream))

	def __eq__(self, o: object) -> bool:
		if isinstance(o, OggResource):
			return self.stream == o.stream and self.path.resolve() == o.path.resolve()
		return NotImplemented


class _Namespace:
	pass


class _Registry:
	def __init__(self) -> None:
		self.items = _Namespace()
		self._key = 0

	def make(self, name: str) -> int:
		if name.startswith("_"):
			raise ValueError("Item names may not begin with an underscore!")
		if hasattr(self, name):
			raise ValueError(f"Item of name `{name!r}` already exists!")

		self._key += 1
		setattr(self.items, name, self._key)
		return self._key


class AbstractAssetRouter:
	"""
	An asset router converts a request for a resource with optional
	and varying arguments into final results.
	They can be stacked through asset systems to influence the loading
	behavior of different assets.

	### Attempted explanation:
	All asset router creations and invocations are caused by a call
	to `load_asset(a, [x, y, z, ...])` which determined that `a`
	must be loaded with a router since it was dictated so by an
	asset system.
	The router's route functions as returned by its `get_route_funcs`
	method are then called in order where:
	- The first one receives `a, x, y, z` as its arguments and returns
	  a sequence `s_0` of resources.
	- The `n`th one receives the loaded resources of router function
	  `n-1` in its args and returns another sequence `s_n` of
	  resources.
	- The last one receives the loaded resources of the preceding
	  router function and may return anything, a final result to which
	  the call to `load_asset` ultimately evaluates to.
	
	All router functions except for the last one must return subclasses
	of `Resource`.
	To pass information between route functions, simply write whatever
	you need into `self` and then access it later.
	The functions will be called in order they appear in in the
	iterable returned from `get_route_funcs`.
	It is unwise to load more assets in routing functions since you may
	end up in recursive cycles. `self.asm.resolve_asset_raw` however
	should be safe.
	"""
	def __init__(self, asm: "_AssetSystemManager") -> None:
		"""
		Initializes a router for usage.
		:param asm: The AssetSystemManager that created this router.
		"""
		self.asm = asm

	def get_route_funcs(self) -> t.Iterable[t.Callable]:
		"""
		Returns this asset router's routing functions.
		"""
		raise NotImplementedError("Subclass this!")


class _DefaultAssetRouter(AbstractAssetRouter):
	def get_route_funcs(self):
		return (self.route, self.route_unpack)

	def route(self, whatever: t.Any) -> t.Sequence[Resource]:
		if not isinstance(whatever, Resource):
			raise TypeError(f"Default asset router received non-resource: {whatever!r}!")
		return (whatever,)

	def route_unpack(self, res) -> t.Any:
		return res


class AssetSystemEntry:
	__slots__ = ("value", "router_id")

	def __init__(self, value: t.Any, router_id: int = None) -> None:
		self.value = value
		self.router_id = router_id


class AssetSystem:
	"""
	An asset system maps asset identifiers to either:
	- Concrete resources
	- Arbitrary values that can be more complicatedly resolved to
	  resources by funneling them through asset routers.
	Also, it maps router identifiers to router classes.
	"""

	def __init__(
		self,
		asset_map: t.Dict[int, t.Any],
		router_map: t.Dict[int, t.Type[AbstractAssetRouter]]
	) -> None:
		for k, v in asset_map.items():
			if isinstance(v, AssetSystemEntry):
				continue
			asset_map[k] = AssetSystemEntry(v)
		self.asset_map: t.Dict[int, AssetSystemEntry] = asset_map

		if any(not issubclass(v, AbstractAssetRouter) for v in router_map.values()):
			raise TypeError("Non-Asset Router supplied to Asset System's router map!")
		self.router_map = router_map


class _AssetSystemManager():
	"""
	Singleton class for holding the active asset systems,
	an asset registry as well as the source asset directory.
	"""
	def __init__(self) -> None:
		self.asset_system_stack: t.List[AssetSystem] = []

		self._asset_registry = _Registry()
		self._router_registry = _Registry()
		self._routers: t.Dict[int, AbstractAssetRouter] = {}

		self.asset_dir = Path.cwd() / "assets"
		self._cache: t.Dict[Resource, t.Any] = {}

		self._hinted_tex_bin: t.Dict[t.Hashable, TextureBin] = defaultdict(TextureBin)
		self._tex_bin = TextureBin()

	def add_asset_system(self, asset_system: AssetSystem) -> None:
		"""
		Adds an asset system to the asset system stack, which may
		influence the path assets are retrieved from via `load_asset`.
		Also invalidates the asset system manager's cache.
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

	def resolve_asset_raw(self, asset_id: int) -> AssetSystemEntry:
		"""
		Resolves an asset to a an asset system entry depending
		on the current asset system stack.
		No routers are invoked, this is whatever was directly written
		into an asset system.
		"""
		for i in range(len(self.asset_system_stack) - 1, -1, -1):
			as_ = self.asset_system_stack[i]
			if asset_id in as_.asset_map:
				return as_.asset_map[asset_id]

		raise AssetNotFoundError(f"Asset {asset_id} not found in registered asset systems.")

	def resolve_router(self, router_id: t.Optional[int]) -> AbstractAssetRouter:
		"""
		Resolves the router type of the given router id, based
		on the current asset system stack, and returns an instance of
		it.
		If `router_id` is `None`, the default asset router will be
		returned.
		"""
		if router_id is None:
			return _DefaultAssetRouter(self)

		for i in range(len(self.asset_system_stack) - 1, -1, -1):
			as_ = self.asset_system_stack[i]
			if router_id in as_.router_map:
				return as_.router_map[router_id](self)

		raise RouterNotFoundError(
			f"Router for router id {router_id} not found in "
			f"registered asset systems."
		)

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
		except AllocatorException:
			# NOTE: idk how OpenGL handles textures it can't fit into an
			# atlas, probably horribly slowly but whatever
			return (img, False)

	def load_asset(self, asset: t.Hashable, *args, cache: bool = True) -> t.Any:
		"""
		Loads the given asset in the context of the current asset system
		stack.
		The kwarg `cache` can be set to prevent caching of any loaded
		resources.
		"""
		ase = self.resolve_asset_raw(asset)
		router = self.resolve_router(ase.router_id)
		*r_funcs, final_func = router.get_route_funcs()

		route_in = (ase.value, *args)
		for f in r_funcs:
			route_out = f(*route_in)
			route_in = tuple(self._load_resource(res, cache) for res in route_out)

		return final_func(*route_in)

	def _load_resource(self, res: Resource, cache: bool = True) -> t.Any:
		"""
		Loads the given resource directly, without resolving anything.
		"""
		if res in self._cache:
			return self._cache[res]

		result = res.load(self)
		if cache:
			self._cache[res] = result
		return result

	def invalidate_cache(self, entries: t.Optional[t.Iterable[Resource]] = None) -> None:
		"""
		Invalidates the asset system's cache.
		If an iterable of resources is specified, only those will
		be removed from the cache, otherwise the entire cache is
		cleared.
		"""
		if entries:
			for e in entries:
				self._cache.pop(e, None) # don't error on nonexistent cache entries
		else:
			self._cache.clear()

	def register_assets(self, *names: str) -> None:
		"""
		Registers the given names as asset names, making them appear in
		`ASSET`. ValueErrors are raised on duplicate names and they
		may not begin with underscores. *SCREAM_CASE* is encouraged.
		"""
		for name in names:
			self._asset_registry.make(name)

	def register_routers(self, *names: str) -> None:
		"""
		Registers the given names as router names, making them appear
		in `ASSET_ROUTERS`. ValueErrors are raised on duplicate names
		and they may not begin with underscores. *SCREAM_CASE* is
		encouraged.
		"""
		for name in names:
			self._router_registry.make(name)

_asm = _AssetSystemManager()

add_asset_system = _asm.add_asset_system
remove_asset_system = _asm.remove_asset_system
load_asset = _asm.load_asset
invalidate_cache = _asm.invalidate_cache
register_assets = _asm.register_assets
register_routers = _asm.register_routers

ASSET = _asm._asset_registry.items
ASSET_ROUTER = _asm._router_registry.items
