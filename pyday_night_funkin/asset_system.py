"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from enum import IntEnum
from pathlib import Path
import json
import typing as t

from pyglet.image import AbstractImage
from pyglet.media import load as load_media, Source

from pyday_night_funkin.constants import DIFFICULTY
from pyday_night_funkin.image_loader import (
	FrameInfoTexture, load_frames_from_sparrow_atlas, load_image
)
import pyday_night_funkin.ogg_decoder


# NOTE: Instead of having the complete assets be an ASSETS class with Resources,
# these resources having different paths for each asset, create each asset system
# as its own class having each resource registered with exactly one path each.
# That would also allow for cool modding where one could supply an incomplete asset
# system with a higher priority than an existing one, replacing specific resources.


class ASSET_SYSTEM(IntEnum):
	"""
	Contains an enum value for each asset system supported by
	PydayNightFunkin and the common sprites.

	STANDARD: The "default" asset system, as seen in the Funkin github
	repo. (master, commit 8bd9126a, ~ May 16 2021).
	"""
	STANDARD = 0


class _AssetSystemManager():
	"""
	Small singleton class solely for holding the active asset system
	as well as the source asset directory.
	"""
	def __init__(self) -> None:
		self.active_asset_system = ASSET_SYSTEM.STANDARD
		self.asset_dir =  Path.cwd() / "assets"


_asm = _AssetSystemManager()

def set_active_asset_system(asset_system: ASSET_SYSTEM) -> None:
	"""
	Sets the active asset system, which will influence the loading
	paths of all assets in `ASSETS`.
	"""
	_asm.active_asset_system = asset_system

def get_active_asset_system() -> ASSET_SYSTEM:
	"""
	Returns the active asset system.
	"""
	return _asm.active_asset_system

def get_asset_directory() -> Path:
	"""
	Returns the root asset directory.
	"""
	return _asm.asset_dir


class Resource():
	def __init__(
		self,
		first: t.Union[str, Path, t.Dict[ASSET_SYSTEM, t.Union[str, Path]]],
		*paths: t.Union[str, Path],
	) -> None:
		"""
		Creates a resource. This can be done in two ways:
		- A dict can be supplied mapping each asset system to a path
		for the resource.
		- An amount of n paths can be supplied where n has to be the
		amount of supported asset systems. The paths will be mapped
		together with the asset systems in the order they are defined
		in the `ASSET_SYSTEM` enum.
		"""
		if isinstance(first, dict):
			if paths:
				raise TypeError("Can't combine paths with given asset path dict.")
			self.paths = first
		else:
			paths = (first, ) + paths

		if len(paths) != len(ASSET_SYSTEM):
			raise ValueError("Resource must receive a path for every asset system")
		self.paths = dict(zip(ASSET_SYSTEM, paths))

	def get_path(self) -> Path:
		if not _asm.active_asset_system in self.paths:
			raise FileNotFoundError(
				f"Asset not available for current asset system "
				f"{ASSET_SYSTEM(_asm.active_asset_system).name!r}."
			)
		return _asm.asset_dir / self.paths[_asm.active_asset_system]

	def load(self) -> None:
		raise NotImplementedError("Must by defined by Resource subclass.")


class XmlTextureAtlas(Resource):
	def load(self) -> t.Dict[str, t.List[FrameInfoTexture]]:
		return load_frames_from_sparrow_atlas(self.get_path())


class Image(Resource):
	def load(self) -> AbstractImage:
		return load_image(self.get_path())


class OggVorbis(Resource):

	_decoder = pyday_night_funkin.ogg_decoder.get_decoders()[0]

	def _load(self, path: Path, streaming_source: bool) -> Source:
		return load_media(str(path), None, streaming_source, self._decoder)


class OggVorbisSound(OggVorbis):
	def load(self, streaming_source: bool = False) -> Source:
		return self._load(self.get_path(), streaming_source)


class OggVorbisSong(OggVorbis):
	def __init__(self, song_dir: "AssetPath", data_dir: "AssetPath", *args, **kwargs) -> None:
		"""
		Creates a song resource. They are handled differently than the
		other resources, needing a song directory `AssetPath` resource
		in the constructor, which will be used to resolve the song
		directory, as well as a data directory, used for opening the
		song's json file.
		The per-asset system paths here must be fragments and will be
		appended to the song directory path. They should be strings
		as they will be concatted to build json file names.
		Some songs may only consist out of an instrumental, in which
		case `load`'s 2nd return value will be `None`.
		"""
		super().__init__(*args, **kwargs)
		self.song_dir = song_dir
		self.data_dir = data_dir

	def get_path(self) -> str:
		return str(self.paths[_asm.active_asset_system])

	def load(
		self,
		stream: t.Tuple[bool, bool],
		difficulty: DIFFICULTY
	) -> t.Tuple[Source, t.Optional[Source], t.Dict[str, t.Any]]:
		json_file = str(self.get_path()) + difficulty.to_song_json_suffix() + ".json"
		json_path = self.data_dir.load() / self.get_path() / json_file
		song_path = self.song_dir.load() / self.get_path() / "Inst.ogg"
		voic_path = self.song_dir.load() / self.get_path() / "Voices.ogg"
		with open(json_path, "r") as json_handle:
			# TODO verify integrity of song dict
			data = json.load(json_handle)
		inst = self._load(song_path, stream[0])
		voic = None
		if data["song"]["needsVoices"]:  # Should be more like "hasVoices":
			voic = self._load(voic_path, stream[1])

		return (inst, voic, data)


class AssetPath(Resource):
	def load(self) -> Path:
		return self.get_path()


_SONG_DIR = AssetPath("songs/")
_DATA_DIR = AssetPath("preload/data/")

class ASSETS:
	"""
	Resources that make up the base game and tend to be located in
	different places in different asset systems.
	This class exists solely for the sake of namespacing and contains
	three sub-classes, `XML`, `IMG` and `SND` whose class attributes
	are the game's resources.
	"""
	class XML:
		BOYFRIEND = XmlTextureAtlas("shared/images/BOYFRIEND.xml",)
		GIRLFRIEND = XmlTextureAtlas("shared/images/GF_assets.xml")
		DADDY_DEAREST = XmlTextureAtlas("shared/images/DADDY_DEAREST.xml")
		ICON_GRID = XmlTextureAtlas("preload/images/iconGrid.xml")
		NOTES = XmlTextureAtlas("shared/images/NOTE_assets.xml")

	class IMG:
		STAGE_BACK = Image("shared/images/stageback.png")
		STAGE_FRONT = Image("shared/images/stagefront.png")
		STAGE_CURTAINS = Image("shared/images/stagecurtains.png")
		HEALTH_BAR = Image("shared/images/healthBar.png")
		READY = Image("shared/images/ready.png")
		SET = Image("shared/images/set.png")
		GO = Image("shared/images/go.png")
		SICK = Image("shared/images/sick.png")
		GOOD = Image("shared/images/good.png")
		BAD = Image("shared/images/bad.png")
		SHIT = Image("shared/images/shit.png")
		NUM0 = Image("preload/images/num0.png")
		NUM1 = Image("preload/images/num1.png")
		NUM2 = Image("preload/images/num2.png")
		NUM3 = Image("preload/images/num3.png")
		NUM4 = Image("preload/images/num4.png")
		NUM5 = Image("preload/images/num5.png")
		NUM6 = Image("preload/images/num6.png")
		NUM7 = Image("preload/images/num7.png")
		NUM8 = Image("preload/images/num8.png")
		NUM9 = Image("preload/images/num9.png")

	class SOUND:
		INTRO_3 = OggVorbisSound("shared/sounds/intro3.ogg")
		INTRO_2 = OggVorbisSound("shared/sounds/intro2.ogg")
		INTRO_1 = OggVorbisSound("shared/sounds/intro1.ogg")
		INTRO_GO = OggVorbisSound("shared/sounds/introGo.ogg")

	class PATH:
		SONGS = _SONG_DIR

	class SONG:
		TUTORIAL = OggVorbisSong(_SONG_DIR, _DATA_DIR, "tutorial")
		BOPEEBO = OggVorbisSong(_SONG_DIR, _DATA_DIR, "bopeebo")
		FRESH = OggVorbisSong(_SONG_DIR, _DATA_DIR, "fresh")
		DAD_BATTLE = OggVorbisSong(_SONG_DIR, _DATA_DIR, "dadbattle")
