"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from collections import defaultdict
import json
from pathlib import Path
import re
import sys
import typing as t
from xml.etree.ElementTree import ElementTree

from loguru import logger
from pyglet import image
from pyglet.image.atlas import AllocatorException, TextureBin
from pyglet import media

from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser
from pyday_night_funkin.core import ogg_decoder
from pyday_night_funkin.utils import FrameInfoTexture

if t.TYPE_CHECKING:
	from pyglet.image import AbstractImage, Texture
	from pyday_night_funkin.enums import DIFFICULTY


RE_SPLIT_ANIMATION_NAME = re.compile(r"^(.*)(\d{4})$")
ADDRESS_PADDING = (sys.maxsize.bit_length() + 1) // 4


class AssetNotFoundError(ValueError):
	pass


class ASSETS:
	"""
	Assets that make up the base game and tend to be located in
	different places in different asset systems.
	This class exists solely for the sake of namespacing and contains
	multiple sub-classes.
	"""
	class XML:
		BOYFRIEND = 0
		GIRLFRIEND = 1
		DADDY_DEAREST = 2
		NOTES = 3
		ALPHABET = 4
		GAME_LOGO = 5
		TITLE_ENTER = 6
		TITLE_GIRLFRIEND = 7
		MAIN_MENU_ASSETS = 8
		STORY_MENU_CHARACTERS = 9
		STORY_MENU_UI = 10

	class IMG:
		STAGE_BACK = 100000
		STAGE_FRONT = 100001
		STAGE_CURTAINS = 100002
		HEALTH_BAR = 100003
		READY = 100004
		SET = 100005
		GO = 100006
		SICK = 100007
		GOOD = 100008
		BAD = 100009
		SHIT = 100010
		NUM0 = 100011
		NUM1 = 100012
		NUM2 = 100013
		NUM3 = 100014
		NUM4 = 100015
		NUM5 = 100016
		NUM6 = 100017
		NUM7 = 100018
		NUM8 = 100019
		NUM9 = 100020
		NEWGROUNDS_LOGO = 100021
		MENU_BG = 100022
		MENU_DESAT = 100023
		MENU_BG_BLUE = 100024
		ICON_GRID = 100025

	class SOUND:
		INTRO_3 = 200000
		INTRO_2 = 200001
		INTRO_1 = 200002
		INTRO_GO = 200003
		MENU_CONFIRM = 200004
		MENU_SCROLL = 200005

	class PATH:
		SONGS = 300000
		DATA = 300001

	class SONG:
		TUTORIAL = 400000
		BOPEEBO = 400001
		FRESH = 400002
		DAD_BATTLE = 400003

	class MUSIC:
		MENU = 500001

	class TXT:
		INTRO_TEXT = 600001


class Resource():
	"""
	A resource is a class representing a relative file location on disk.
	They are compared and hashed by the path they point to.
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
		"""
		Loads the asset in the context of the given asset system manager.
		"""
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


class AssetPath(Resource):
	def load(self, asm: "_AssetSystemManager") -> Path:
		return self.get_full_path(asm)


class Image(Resource):
	def __init__(
		self,
		path: t.Union[str, Path],
		atlas_hint: t.Optional[t.Hashable] = None,
	) -> None:
		"""
		Creates an image. The path will be passed on to the Resource
		constructor as usual, but the atlas_hint can be used to try
		and place images in a common texture atlas.
		"""
		super().__init__(path)
		self._atlas_hint = atlas_hint

	def load(self, asm: "_AssetSystemManager") -> "Texture":
		return asm.store_image(
			image.load(self.get_full_path(asm)),
			self._atlas_hint,
		)[0].get_texture()


class TextFile(Resource):
	def load(self, asm: "_AssetSystemManager", mode: str = "r", *open_args) -> str:
		with open(self.get_full_path(asm), mode, *open_args) as f:
			return f.read()


class JSONFile(Resource):
	def load(self, asm: "_AssetSystemManager") -> t.Any:
		with open(self.get_full_path(asm), "r") as f:
			return json.load(f)


class OggVorbis(Resource):
	_decoder = ogg_decoder.get_decoders()[0]

	def load(
		self,
		asm: "_AssetSystemManager",
		streaming_source: bool = False,
	) -> media.Source:
		return media.load(
			str(self.get_full_path(asm)),
			streaming = streaming_source,
			decoder = self._decoder,
		)


class OggVorbisSong(OggVorbis):
	def __init__(self, name: str) -> None:
		"""
		Creates a song resource. They are handled differently than the
		other resources and will set their path to `""`.
		Songs query the data and song directory from the current asset
		system context and read their data and ogg files from there.

		Some songs may only consist out of an instrumental, in which
		case `load`'s 2nd return value will be `None`.
		"""
		super().__init__("")
		self.name = name

	def load(
		self,
		asm: "_AssetSystemManager",
		stream: t.Tuple[bool, bool],
		difficulty: "DIFFICULTY",
	) -> t.Tuple[media.Source, t.Optional[media.Source], t.Dict[str, t.Any]]:
		data_dir = asm.resolve_resource(ASSETS.PATH.DATA).path
		song_dir = asm.resolve_resource(ASSETS.PATH.SONGS).path
		json_path = data_dir / self.name / f"{self.name}{difficulty.to_song_json_suffix()}.json"
		song_path = song_dir / self.name / "Inst.ogg"
		voic_path = song_dir / self.name / "Voices.ogg"

		data = asm.load_direct(JSONFile(json_path))
		# TODO verify integrity of song dict
		data = data["song"]

		return (
			asm.load_direct(OggVorbis(song_path), stream[0]),
			# Should be more like "hasVoices":
			asm.load_direct(OggVorbis(voic_path), stream[1]) if data["needsVoices"] else None,
			data,
		)

	def __eq__(self, o: object) -> bool:
		if isinstance(o, OggVorbisSong):
			return self.name == o.name
		return NotImplemented

	def __hash__(self) -> int:
		return hash(self.name)

	def __repr__(self) -> str:
		return (
			f"<{self.__class__.__name__} {self.name!r} at "
			f"0x{id(self):0>{ADDRESS_PADDING}X}>"
		)

class XmlTextureAtlas(Resource):
	def load(self, asm: "_AssetSystemManager") -> t.Dict[str, t.List[FrameInfoTexture]]:
		xml_path = self.get_full_path(asm)
		et = ElementTree()
		with open(xml_path, "r", encoding="utf-8") as fp:
			et.parse(fp, AlmostXMLParser())

		texture_atlas = et.getroot() # Should be a TextureAtlas node
		texture_region_cache = {}
		image_resource = Image(self.path.parent / texture_atlas.attrib["imagePath"])
		atlas_surface: "Texture" = asm.load_direct(image_resource)

		frame_sequences: t.DefaultDict[str, t.List[FrameInfoTexture]] = defaultdict(list)
		for sub_texture in texture_atlas:
			if sub_texture.tag != "SubTexture":
				logger.warning(f"Expected 'SubTexture' tag, got {sub_texture.tag!r}. Skipping.")
				continue

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
					f"{(name, region, frame_vars)} Invalid attributes for SubTexture entry. Skipping."
				)
				continue

			if (match_res := RE_SPLIT_ANIMATION_NAME.match(name)) is None:
				logger.warning(f"Invalid SubTexture name in {xml_path.name}: {name!r}")
				continue

			animation_name = match_res[1]
			frame_id = int(match_res[2])
			if frame_id > len(frame_sequences[animation_name]):
				logger.warning(
					f"Frames for animation {animation_name!r} inconsistent: current is "
					f"frame {frame_id}, but only {len(frame_sequences[animation_name])} frames "
					f"exist so far."
				)

			x, y, w, h = region = tuple(int(e) for e in region)
			frame_vars = tuple(None if e is None else int(e) for e in frame_vars)
			if region not in texture_region_cache:
				texture_region_cache[region] = atlas_surface.get_region(
					x, atlas_surface.height - h - y, w, h,
				)
			has_frame_vars = frame_vars[0] is not None
			frame_sequences[animation_name].append(
				FrameInfoTexture(texture_region_cache[region], has_frame_vars, frame_vars)
			)

		return dict(frame_sequences) # Don't return a defaultdict!


class AssetSystem():
	"""
	An asset system is pretty much just a dict mapping asset enum values
	to their actual resources.
	"""
	def __init__(self, asset_res_map: t.Dict[t.Hashable, Resource]) -> None:
		self._asset_res_map = asset_res_map

	def __contains__(self, x: t.Hashable) -> bool:
		return x in self._asset_res_map

	def __len__(self) -> int:
		return len(self._asset_res_map)

	def __getitem__(self, x: t.Hashable) -> Resource:
		return self._asset_res_map[x]

	@property
	def assets(self):
		return self._asset_res_map.keys()


# The "default" asset system, as seen in the Funkin github
# repo. (master, commit 8bd9126a, ~ May 16 2021).
_DEFAULT_ASSET_SYSTEM = AssetSystem({
	ASSETS.XML.BOYFRIEND: XmlTextureAtlas("shared/images/BOYFRIEND.xml"),
	ASSETS.XML.GIRLFRIEND: XmlTextureAtlas("shared/images/GF_assets.xml"),
	ASSETS.XML.DADDY_DEAREST: XmlTextureAtlas("shared/images/DADDY_DEAREST.xml"),
	ASSETS.XML.NOTES: XmlTextureAtlas("shared/images/NOTE_assets.xml"),
	ASSETS.XML.ALPHABET: XmlTextureAtlas("preload/images/alphabet.xml"),
	ASSETS.XML.GAME_LOGO: XmlTextureAtlas("preload/images/logoBumpin.xml"),
	ASSETS.XML.TITLE_ENTER: XmlTextureAtlas("preload/images/titleEnter.xml"),
	ASSETS.XML.TITLE_GIRLFRIEND: XmlTextureAtlas("preload/images/gfDanceTitle.xml"),
	ASSETS.XML.MAIN_MENU_ASSETS: XmlTextureAtlas("preload/images/FNF_main_menu_assets.xml"),
	ASSETS.XML.STORY_MENU_CHARACTERS: XmlTextureAtlas("preload/images/campaign_menu_UI_characters.xml"),
	ASSETS.XML.STORY_MENU_UI: XmlTextureAtlas("preload/images/campaign_menu_UI_assets.xml"),

	ASSETS.IMG.STAGE_BACK: Image("shared/images/stageback.png"),
	ASSETS.IMG.STAGE_FRONT: Image("shared/images/stagefront.png"),
	ASSETS.IMG.STAGE_CURTAINS: Image("shared/images/stagecurtains.png"),
	ASSETS.IMG.HEALTH_BAR: Image("shared/images/healthBar.png"),
	ASSETS.IMG.READY: Image("shared/images/ready.png"),
	ASSETS.IMG.SET: Image("shared/images/set.png"),
	ASSETS.IMG.GO: Image("shared/images/go.png"),
	ASSETS.IMG.SICK: Image("shared/images/sick.png", 0), # Throw all of these into the same atlas
	ASSETS.IMG.GOOD: Image("shared/images/good.png", 0), # For more efficient combo sprite
	ASSETS.IMG.BAD: Image("shared/images/bad.png", 0),   # rendering
	ASSETS.IMG.SHIT: Image("shared/images/shit.png", 0),
	ASSETS.IMG.NUM0: Image("preload/images/num0.png", 0),
	ASSETS.IMG.NUM1: Image("preload/images/num1.png", 0),
	ASSETS.IMG.NUM2: Image("preload/images/num2.png", 0),
	ASSETS.IMG.NUM3: Image("preload/images/num3.png", 0),
	ASSETS.IMG.NUM4: Image("preload/images/num4.png", 0),
	ASSETS.IMG.NUM5: Image("preload/images/num5.png", 0),
	ASSETS.IMG.NUM6: Image("preload/images/num6.png", 0),
	ASSETS.IMG.NUM7: Image("preload/images/num7.png", 0),
	ASSETS.IMG.NUM8: Image("preload/images/num8.png", 0),
	ASSETS.IMG.NUM9: Image("preload/images/num9.png", 0),
	ASSETS.IMG.NEWGROUNDS_LOGO: Image("preload/images/newgrounds_logo.png"),
	ASSETS.IMG.MENU_BG: Image("preload/images/menuBG.png"),
	ASSETS.IMG.MENU_DESAT: Image("preload/images/menuDesat.png"),
	ASSETS.IMG.MENU_BG_BLUE: Image("preload/images/menuBGBlue.png"),
	ASSETS.IMG.ICON_GRID: Image("preload/images/iconGrid.png"),

	ASSETS.SOUND.INTRO_3: OggVorbis("shared/sounds/intro3.ogg"),
	ASSETS.SOUND.INTRO_2: OggVorbis("shared/sounds/intro2.ogg"),
	ASSETS.SOUND.INTRO_1: OggVorbis("shared/sounds/intro1.ogg"),
	ASSETS.SOUND.INTRO_GO: OggVorbis("shared/sounds/introGo.ogg"),
	ASSETS.SOUND.MENU_CONFIRM: OggVorbis("preload/sounds/confirmMenu.ogg"),
	ASSETS.SOUND.MENU_SCROLL: OggVorbis("preload/sounds/scrollMenu.ogg"),

	ASSETS.PATH.SONGS: AssetPath("songs/"),
	ASSETS.PATH.DATA: AssetPath("preload/data/"),

	ASSETS.SONG.TUTORIAL: OggVorbisSong("tutorial"),
	ASSETS.SONG.BOPEEBO: OggVorbisSong("bopeebo"),
	ASSETS.SONG.FRESH: OggVorbisSong("fresh"),
	ASSETS.SONG.DAD_BATTLE: OggVorbisSong("dadbattle"),

	ASSETS.MUSIC.MENU: OggVorbis("preload/music/freakyMenu.ogg"),

	ASSETS.TXT.INTRO_TEXT: TextFile("preload/data/introText.txt"),
})


class _AssetSystemManager():
	"""
	Small singleton class for holding the active asset systems
	as well as the source asset directory.
	Will be created with the default asset system as its only one.
	"""
	def __init__(self) -> None:
		self.asset_system_stack = []
		self.add_asset_system(_DEFAULT_ASSET_SYSTEM)

		self.asset_dir = Path.cwd() / "assets"
		self._cache: t.Dict[Resource, t.Any] = {}

		self._hinted_tex_bin: t.Dict[t.Hashable, TextureBin] = defaultdict(TextureBin)
		self._tex_bin = TextureBin()

	def add_asset_system(self, asset_system: AssetSystem) -> None:
		"""
		Adds an asset system to the asset system stack, which may
		influence the path assets are retrieved from via `load_asset`.
		"""
		self.asset_system_stack.append(asset_system)

	def remove_asset_system(self, asset_system: AssetSystem) -> None:
		"""
		Removes an asset system.
		"""
		try:
			self.asset_system_stack.remove(asset_system)
		except ValueError:
			pass

	def resolve_resource(self, asset: t.Hashable) -> Resource:
		"""
		Resolves the resource for the given asset depending on the
		current asset system stack.
		"""
		for i in range(len(self.asset_system_stack) - 1, -1, -1):
			as_ = self.asset_system_stack[i]
			if asset in as_:
				return as_[asset]

		raise AssetNotFoundError(f"Asset {asset} not found in registered asset systems.")

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

	def load_asset(self, asset: t.Hashable, *args, cache: bool = True, **kwargs) -> t.Any:
		"""
		Loads the given asset in the context of the current asset system
		stack.
		The kwarg `cache` can be set to prevent caching of this asset.
		All other args and kwargs will be passed through to the
		resource's `load` method, if it can be found.
		"""
		return self.load_direct(self.resolve_resource(asset), *args, cache=cache, **kwargs)

	def load_direct(self, res: Resource, *args, cache: bool = True, **kwargs) -> t.Any:
		"""
		Loads the given resource directly, bypassing the
		asset -> resource resolving step.
		"""
		if res in self._cache:
			return self._cache[res]

		result = res.load(self, *args, **kwargs)
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

_asm = _AssetSystemManager()

add_asset_system = _asm.add_asset_system
remove_asset_system = _asm.remove_asset_system
load_asset = _asm.load_asset
invalidate_cache = _asm.invalidate_cache
