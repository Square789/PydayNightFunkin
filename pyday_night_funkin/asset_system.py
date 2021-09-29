"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from pathlib import Path
import json
import typing as t

from pyglet.image import AbstractImage
from pyglet.media import load as load_media, Source

from pyday_night_funkin.image_loader import (
	FrameInfoTexture, load_frames_from_texture_atlas, load_image
)
import pyday_night_funkin.ogg_decoder

if t.TYPE_CHECKING:
	from pyday_night_funkin.enums import DIFFICULTY


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
		ICON_GRID = 3
		NOTES = 4

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

	class SOUND:
		INTRO_3 = 200000
		INTRO_2 = 200001
		INTRO_1 = 200002
		INTRO_GO = 200003

	class PATH:
		SONGS = 300000
		DATA = 300001

	class SONG:
		TUTORIAL = 400000
		BOPEEBO = 400001
		FRESH = 400002
		DAD_BATTLE = 400003


class Resource():
	def load(self) -> None:
		raise NotImplementedError("Must by defined by Resource subclass.")


class FileResource(Resource):
	def __init__(self, path: t.Union[str, Path]) -> None:
		"""
		Creates a resource to be found at the given path.
		"""
		self.path = path

	def get_path(self) -> Path:
		"""
		Returns a path that is the concatted path of the absolute root
		asset directory and this resource's path. 
		"""
		return _asm.asset_dir / self.path


class LazyResource(Resource):
	def __init__(self, asset: "ASSETS") -> None:
		"""
		Creates a resource that is lazily fetched in the context of the
		then current asset system stack.
		"""
		self.asset = asset

	def load(self) -> t.Any:
		return load_asset(self.asset)


class AssetPath(FileResource):
	def load(self) -> Path:
		return self.get_path()


class XmlTextureAtlas(FileResource):
	def load(self) -> t.Dict[str, t.List[FrameInfoTexture]]:
		return load_frames_from_texture_atlas(self.get_path())


class Image(FileResource):
	def load(self) -> AbstractImage:
		return load_image(self.get_path())


class OggVorbis(FileResource):
	_decoder = pyday_night_funkin.ogg_decoder.get_decoders()[0]

	def _load(self, path: Path, streaming_source: bool) -> Source:
		return load_media(str(path), None, streaming_source, self._decoder)


class OggVorbisSound(OggVorbis):
	def load(self, streaming_source: bool = False) -> Source:
		return self._load(self.get_path(), streaming_source)


class OggVorbisSong(OggVorbis):
	def __init__(self, name: str) -> None:
		"""
		Creates a song resource. They are handled differently than the
		other resources and `get_path` will fail for them.
		Songs query the data and song directory from the current asset
		system context and read their data and ogg files from there.

		Some songs may only consist out of an instrumental, in which
		case `load`'s 2nd return value will be `None`.
		"""
		super().__init__(None)
		self.name = name

	def load(
		self,
		stream: t.Tuple[bool, bool],
		difficulty: "DIFFICULTY",
	) -> t.Tuple[Source, t.Optional[Source], t.Dict[str, t.Any]]:
		data_dir = load_asset(ASSETS.PATH.DATA)
		song_dir = load_asset(ASSETS.PATH.SONGS)
		json_path = data_dir / self.name / f"{self.name}{difficulty.to_song_json_suffix()}.json"
		song_path = song_dir / self.name / "Inst.ogg"
		voic_path = song_dir / self.name / "Voices.ogg"
		with open(json_path, "r") as json_handle:
			# TODO verify integrity of song dict
			data = json.load(json_handle)["song"]
		inst = self._load(song_path, stream[0])
		voic = None
		if data["needsVoices"]:  # Should be more like "hasVoices":
			voic = self._load(voic_path, stream[1])

		return (inst, voic, data)

# Just a dict wrapped in a class, mostly.
class AssetSystem():
	def __init__(self, asset_res_map: t.Dict["ASSETS", "Resource"]) -> None:
		self.asset_res_map = asset_res_map

	def load_asset(self, asset: "ASSETS", *args, **kwargs) -> t.Any:
		if asset not in self.asset_res_map:
			return None
		return self.asset_res_map[asset].load(*args, **kwargs)


# The "default" asset system, as seen in the Funkin github
# repo. (master, commit 8bd9126a, ~ May 16 2021).
_DEFAULT_ASSET_SYSTEM = AssetSystem({
	ASSETS.XML.BOYFRIEND: XmlTextureAtlas("shared/images/BOYFRIEND.xml"),
	ASSETS.XML.GIRLFRIEND: XmlTextureAtlas("shared/images/GF_assets.xml"),
	ASSETS.XML.DADDY_DEAREST: XmlTextureAtlas("shared/images/DADDY_DEAREST.xml"),
	ASSETS.XML.ICON_GRID: XmlTextureAtlas("preload/images/iconGrid.xml"),
	ASSETS.XML.NOTES: XmlTextureAtlas("shared/images/NOTE_assets.xml"),

	ASSETS.IMG.STAGE_BACK: Image("shared/images/stageback.png"),
	ASSETS.IMG.STAGE_FRONT: Image("shared/images/stagefront.png"),
	ASSETS.IMG.STAGE_CURTAINS: Image("shared/images/stagecurtains.png"),
	ASSETS.IMG.HEALTH_BAR: Image("shared/images/healthBar.png"),
	ASSETS.IMG.READY: Image("shared/images/ready.png"),
	ASSETS.IMG.SET: Image("shared/images/set.png"),
	ASSETS.IMG.GO: Image("shared/images/go.png"),
	ASSETS.IMG.SICK: Image("shared/images/sick.png"),
	ASSETS.IMG.GOOD: Image("shared/images/good.png"),
	ASSETS.IMG.BAD: Image("shared/images/bad.png"),
	ASSETS.IMG.SHIT: Image("shared/images/shit.png"),
	ASSETS.IMG.NUM0: Image("preload/images/num0.png"),
	ASSETS.IMG.NUM1: Image("preload/images/num1.png"),
	ASSETS.IMG.NUM2: Image("preload/images/num2.png"),
	ASSETS.IMG.NUM3: Image("preload/images/num3.png"),
	ASSETS.IMG.NUM4: Image("preload/images/num4.png"),
	ASSETS.IMG.NUM5: Image("preload/images/num5.png"),
	ASSETS.IMG.NUM6: Image("preload/images/num6.png"),
	ASSETS.IMG.NUM7: Image("preload/images/num7.png"),
	ASSETS.IMG.NUM8: Image("preload/images/num8.png"),
	ASSETS.IMG.NUM9: Image("preload/images/num9.png"),

	ASSETS.SOUND.INTRO_3: OggVorbisSound("shared/sounds/intro3.ogg"),
	ASSETS.SOUND.INTRO_2: OggVorbisSound("shared/sounds/intro2.ogg"),
	ASSETS.SOUND.INTRO_1: OggVorbisSound("shared/sounds/intro1.ogg"),
	ASSETS.SOUND.INTRO_GO: OggVorbisSound("shared/sounds/introGo.ogg"),

	ASSETS.PATH.SONGS: AssetPath("songs/"),
	ASSETS.PATH.DATA: AssetPath("preload/data/"),

	ASSETS.SONG.TUTORIAL: OggVorbisSong("tutorial"),
	ASSETS.SONG.BOPEEBO: OggVorbisSong("bopeebo"),
	ASSETS.SONG.FRESH: OggVorbisSong("fresh"),
	ASSETS.SONG.DAD_BATTLE: OggVorbisSong("dadbattle"),
})


class _AssetSystemManager():
	"""
	Small singleton class for holding the active asset systems
	as well as the source asset directory.
	Will be created with the default asset system as its only one.
	"""
	def __init__(self) -> None:
		self._cwd = Path.cwd()
		self.asset_system_stack = [_DEFAULT_ASSET_SYSTEM]
		self.asset_dir = Path.cwd() / "assets"

	def _add_asset_system(self, asset_system: AssetSystem):
		self.asset_system_stack.append(asset_system)

	def _remove_asset_system(self, asset_system: AssetSystem):
		try:
			self.asset_system_stack.remove(asset_system)
		except ValueError:
			pass

	def _load_asset(self, asset: ASSETS, *args, **kwargs) -> t.Any:
		for i in range(len(self.asset_system_stack) - 1, -1, -1):
			res = self.asset_system_stack[i].load_asset(asset, *args, **kwargs)
			if res is not None:
				return res

		raise FileNotFoundError(f"Asset {asset} not found in registered asset systems.")


_asm = _AssetSystemManager()

def add_asset_system(asset_system: AssetSystem) -> None:
	"""
	Adds an asset system to the asset system stack, which may
	influence the path assets are retrieved from via `load_asset`.
	"""
	_asm._add_asset_system(asset_system)

def remove_asset_system(asset_system: AssetSystem) -> None:
	"""
	Removes an asset system.
	"""
	_asm._remove_asset_system(asset_system)

def load_asset(asset: "ASSETS", *args, **kwargs) -> t.Any:
	"""
	Loads the given asset in the context of the current asset system
	stack.
	All args and kwargs will be passed through to the resource's `load`
	method, if it can be found.
	"""
	return _asm._load_asset(asset, *args, **kwargs)

