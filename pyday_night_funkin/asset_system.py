"""
Needlessly overengineered module to redirect the most common
resource's paths based on different asset systems seen throughout the
modding scene's lifetime.
"""
# ^ if i ever get around to implementing a 2nd one, lol

from enum import IntEnum
from pathlib import Path
import typing as t

from pyglet.image import AbstractImage
from pyglet.media import load as load_media, Source

from pyday_night_funkin.image_loader import (
	FrameInfoTexture, load_animation_frames_from_xml, load_image
)
from pyday_night_funkin.ogg_decoder import OggVorbisDecoder


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
		return load_animation_frames_from_xml(self.get_path())


class Image(Resource):
	def load(self) -> AbstractImage:
		return load_image(self.get_path())


class OggVorbisSound(Resource):
	def load(self, streaming_source: bool = False) -> Source:
		return load_media(str(self.get_path()), None, streaming_source, OggVorbisDecoder())


class OggVorbisSong(Resource):
	def __init__(self, song_dir: "AssetPath", *args, **kwargs) -> None:
		"""
		Creates a song resource. They are handled differently than the
		other resources and need a song directory `AssetPath` resource
		that will be used to resolve the song directory.
		The per-asset system paths here must be fragments and will be
		appended to the song directory path.
		"""
		super().__init__(*args, **kwargs)
		self.song_dir = song_dir

	def get_path(self) -> str:
		return str(self.paths[_asm.active_asset_system])

	def load(self) -> None:
		raise NotImplementedError("Use `load_voices` and `load_instrumental` instead!")

	def load_instrumental(self, streaming_source: bool = False) -> Source:
		abs_path = self.song_dir.load() / self.get_path() / "Inst.ogg"
		return load_media(str(abs_path), None, streaming_source, OggVorbisDecoder())

	def load_voices(self, streaming_source: bool = False) -> Source:
		abs_path = self.song_dir.load() / self.get_path() / "Voices.ogg"
		return load_media(str(abs_path), None, streaming_source, OggVorbisDecoder())


class AssetPath(Resource):
	def load(self) -> Path:
		return self.get_path()


_SONG_DIR = AssetPath("songs/")

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

	class IMG:
		STAGE_BACK = Image("shared/images/stageback.png")
		STAGE_FRONT = Image("shared/images/stagefront.png")
		STAGE_CURTAINS = Image("shared/images/stagecurtains.png")
		HEALTH_BAR = Image("shared/images/healthBar.png")
		READY = Image("shared/images/ready.png")
		SET = Image("shared/images/set.png")
		GO = Image("shared/images/go.png")

	class SOUND:
		INTRO_3 = OggVorbisSound("shared/sounds/intro3.ogg")
		INTRO_2 = OggVorbisSound("shared/sounds/intro2.ogg")
		INTRO_1 = OggVorbisSound("shared/sounds/intro1.ogg")
		INTRO_GO = OggVorbisSound("shared/sounds/introGo.ogg")

	class PATH:
		SONGS = _SONG_DIR

	class SONG:
		TUTORIAL = OggVorbisSong(_SONG_DIR, "tutorial")
		BOPEEBO = OggVorbisSong(_SONG_DIR, "bopeebo")
		FRESH = OggVorbisSong(_SONG_DIR, "fresh")
		DAD_BATTLE = OggVorbisSong(_SONG_DIR, "dadbattle")


SONGS = {
	"Tutorial": ASSETS.SONG.TUTORIAL,
	"Bopeebo": ASSETS.SONG.BOPEEBO,
	"Fresh": ASSETS.SONG.FRESH,
	"Dad Battle": ASSETS.SONG.DAD_BATTLE,
}
