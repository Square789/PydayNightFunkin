"""
Specifies the base game's assets and asset routers.
This is meant to be expanded into some sort of modding system,
but what for anyways
"""

from collections import defaultdict
from loguru import logger
import re
import typing as t

import schema

from pyday_night_funkin.asset_system import (
	ASSET, ASSET_ROUTER, AbstractAssetRouter, AssetSystem, AssetSystemEntry as ASE,
	OggResource, ImageResource, JSONResource, PathResource, TextResource, XMLResource,
	FontResource, register_assets, register_routers, add_asset_system
)
from pyday_night_funkin.utils import FrameInfoTexture

if t.TYPE_CHECKING:
	from pathlib import Path
	from xml.etree.ElementTree import ElementTree
	from pyglet.image import Texture
	from pyglet.media import Source
	from pyday_night_funkin.enums import DIFFICULTY


RE_SPLIT_ANIMATION_NAME = re.compile(r"^(.*)(\d{4})$")

SONG_SCHEMA = schema.Schema(
	{
		"song": {
			"song": str,
			"notes": [schema.And(
				{
					"lengthInSteps": int,
					schema.Optional("bpm"): schema.Or(int, float),
					schema.Optional("changeBPM"): bool,
					"mustHitSection": bool,
					"sectionNotes": [[float, int, float]],
					"typeOfSection": int,
					# Keys I've seen that are ignored:
					# altAnim.
					schema.Optional(str): object,
				},
				lambda d: ("bpm" in d) or not ("changeBPM" in d),
			)],
			"bpm": schema.Or(int, float),
			"needsVoices": bool,
			"player1": str,
			"player2": str,
			"speed": schema.Or(int, float),
			# Keys I've seen that are ignored:
			# sections, sectionLengths, validScore.
			schema.Optional(str): object,
		},
	},
	# Sometimes a very scuffed version of ["song"] also exists at the
	# root level. how you end up with that spaghetti bs and sleep calmly
	# knowing it's out in the world is beyond me
	ignore_extra_keys = True,
)


class IconGridRouter(AbstractAssetRouter):
	"""
	Routes an icon grid image and a character string into health icons.

	Loads a two-element tuple of 150px x 150px textures, a character's
	default and losing icon.
	"""

	_CHAR_MAP = dict((
		("bf",                ((   0,   0), ( 150,   0))),
		("spooky",            (( 300,   0), ( 450,   0))),
		("pico",              (( 600,   0), ( 750,   0))),
		("mom",               (( 900,   0), (1050,   0))),
		("tankman",           ((1200,   0), (1350,   0))),
		("face",              ((   0, 150), ( 150, 150))),
		("dad",               (( 300, 150), ( 450, 150))),
		("bf-old",            (( 600, 150), ( 750, 150))),
		("gf",                (( 900, 150), ( 900, 150))),
		("parents-christmas", ((1050, 150), (1200, 150))),
		("monster",           ((1350, 150), (   0, 300))),
		("bf-pixel",          (( 150, 300), ( 150, 300))),
		("senpai",            (( 300, 300), ( 300, 300))),
		("spirit",            (( 450, 300), ( 456, 300))),
	))

	def get_route_funcs(self):
		return (self.route_image, self.route_icon)

	def route_image(self, icon_res: ImageResource, char_name: str) -> ImageResource:
		self.requested_icon: str = char_name
		return (icon_res,)

	def route_icon(self, icon_texture: "Texture") -> t.Tuple["Texture", "Texture"]:
		if icon_texture.width < 1500 or icon_texture.height < 900:
			raise ValueError("Icon grid has invalid shape!")

		return tuple(
			icon_texture.get_region(x, icon_texture.height - 150 - y, 150, 150).get_texture()
			for x, y in self._CHAR_MAP[self.requested_icon]
		)


class SongRouter(AbstractAssetRouter):
	"""
	Routes a song string into song data.
	Depends on the `PATH_DATA` and `PATH_SONGS` asset, which are
	expected to contain path resources.
	Will load a three-tuple of (Source, Source | None, dict); being
	the instrumental source, the voice source and the song data.
	"""

	def get_route_funcs(self):
		return (self.route_paths, self.route_json, self.route_song, self.route_result)

	def route_paths(
		self, _, song_name: str, stream: bool, difficulty: "DIFFICULTY"
	) -> t.Tuple[PathResource, PathResource]:
		self.song_name = song_name
		self.stream = stream
		self.diff = difficulty
		return (
			self.asm.resolve_asset_raw(ASSET.PATH_DATA).value,
			self.asm.resolve_asset_raw(ASSET.PATH_SONGS).value,
		)

	def route_json(self, data_path: "Path", song_path: "Path") -> t.Tuple[JSONResource]:
		self.song_path = song_path
		file = f"{self.song_name}{self.diff.to_song_json_suffix()}.json"
		return (JSONResource(data_path / self.song_name / file),)

	def route_song(self, json_data: t.Dict) -> t.Tuple[OggResource, ...]:
		self.data = SONG_SCHEMA.validate(json_data)["song"]

		song_dir = self.song_path / self.song_name

		resources = (OggResource(song_dir / "Inst.ogg", self.stream),)
		if self.data["needsVoices"]:
			resources += (OggResource(song_dir / "Voices.ogg", self.stream),)
		return resources

	def route_result(
		self,
		inst: "Source",
		voic: t.Optional["Source"] = None,
	) -> t.Tuple["Source", t.Optional["Source"], t.Dict]:
		return (inst, voic, self.data)


class WeekHeaderRouter(AbstractAssetRouter):
	def get_route_funcs(self):
		return (self.route_paths, self.route_header, self.route_unpack)

	def route_paths(self, _, filename: str) -> t.Tuple[PathResource]:
		self.filename = filename
		return (self.asm.resolve_asset_raw(ASSET.PATH_WEEK_HEADERS).value,)

	def route_header(self, path: "Path") -> "ImageResource":
		return (ImageResource(path / self.filename),)

	def route_unpack(self, res: "Texture") -> "Texture":
		return res


class XMLRouter(AbstractAssetRouter):
	"""
	Routes an XMLResource into animation frames.

	Will load a dict mappig animation prefixes to frame sequences.
	"""
	def get_route_funcs(self):
		return (self.route_xml, self.route_image, self.route_frames)

	def route_xml(self, xml_res: XMLResource) -> t.Tuple[XMLResource]:
		self.xml_res_path = xml_res.path
		return (xml_res,)

	def route_image(self, xml: "ElementTree") -> t.Tuple[ImageResource]:
		self.element_tree = xml
		return (ImageResource(self.xml_res_path.parent / xml.getroot().attrib["imagePath"]),)

	def route_frames(self, atlas_texture: "Texture") -> t.Dict[str, t.List[FrameInfoTexture]]:
		texture_region_cache = {}
		frame_sequences: t.DefaultDict[str, t.List[FrameInfoTexture]] = defaultdict(list)
		for sub_texture in self.element_tree.getroot():
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
					f"{(name, region, frame_vars)} Invalid attributes for SubTexture entry. "
					f"Skipping."
				)
				continue

			if (match_res := RE_SPLIT_ANIMATION_NAME.match(name)) is None:
				logger.warning(f"Invalid SubTexture name in {self.xml_res_path.name}: {name!r}")
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
				texture_region_cache[region] = atlas_texture.get_region(
					x, atlas_texture.height - h - y, w, h,
				)
			has_frame_vars = frame_vars[0] is not None
			frame_sequences[animation_name].append(
				FrameInfoTexture(texture_region_cache[region], has_frame_vars, frame_vars)
			)

		return dict(frame_sequences) # Don't return a defaultdict!

def load() -> None:
	"""
	Registers and loads everything required to run the
	base game into the asset system.
	"""

	ASSET_NAMES = (
		"XML_BOYFRIEND",
		"XML_GIRLFRIEND",
		"XML_DADDY_DEAREST",
		"XML_NOTES",
		"XML_ALPHABET",
		"XML_GAME_LOGO",
		"XML_TITLE_ENTER",
		"XML_TITLE_GIRLFRIEND",
		"XML_MAIN_MENU_ASSET",
		"XML_STORY_MENU_CHARACTERS",
		"XML_STORY_MENU_UI",
		"IMG_STAGE_BACK",
		"IMG_STAGE_FRONT",
		"IMG_STAGE_CURTAINS",
		"IMG_HEALTH_BAR",
		"IMG_READY",
		"IMG_SET",
		"IMG_GO",
		"IMG_SICK",
		"IMG_GOOD",
		"IMG_BAD",
		"IMG_SHIT",
		"IMG_NUM0",
		"IMG_NUM1",
		"IMG_NUM2",
		"IMG_NUM3",
		"IMG_NUM4",
		"IMG_NUM5",
		"IMG_NUM6",
		"IMG_NUM7",
		"IMG_NUM8",
		"IMG_NUM9",
		"IMG_NEWGROUNDS_LOGO",
		"IMG_ICON_GRID",
		"IMG_MENU_BG",
		"IMG_MENU_DESAT",
		"IMG_MENU_BG_BLUE",
		"FONT_VCR",
		"SOUND_INTRO_3",
		"SOUND_INTRO_2",
		"SOUND_INTRO_1",
		"SOUND_INTRO_GO",
		"SOUND_LOSS",
		"SOUND_MENU_CONFIRM",
		"SOUND_MENU_SCROLL",
		"MUSIC_MENU",
		"MUSIC_GAME_OVER",
		"MUSIC_GAME_OVER_END",
		"PATH_SONGS",
		"PATH_DATA",
		"PATH_WEEK_HEADERS",
		"TXT_INTRO_TEXT",
		"SONGS",
		"WEEK_HEADERS",
	)

	register_assets(*ASSET_NAMES)
	register_routers("XML", "SONGS", "ICON_GRID", "WEEK_HEADERS")

	# The "default" asset system, as seen in the Funkin github
	# repo. (master, commit 8bd9126a, ~ May 16 2021).
	_DEFAULT_ASSET_SYSTEM = AssetSystem({
		ASSET.XML_BOYFRIEND: ASE(XMLResource("shared/images/BOYFRIEND.xml"), ASSET_ROUTER.XML),
		ASSET.XML_GIRLFRIEND: ASE(XMLResource("shared/images/GF_assets.xml"), ASSET_ROUTER.XML),
		ASSET.XML_DADDY_DEAREST: ASE(XMLResource("shared/images/DADDY_DEAREST.xml"), ASSET_ROUTER.XML),
		ASSET.XML_NOTES: ASE(XMLResource("shared/images/NOTE_assets.xml"), ASSET_ROUTER.XML),
		ASSET.XML_ALPHABET: ASE(XMLResource("preload/images/alphabet.xml"), ASSET_ROUTER.XML),
		ASSET.XML_GAME_LOGO: ASE(XMLResource("preload/images/logoBumpin.xml"), ASSET_ROUTER.XML),
		ASSET.XML_TITLE_ENTER: ASE(XMLResource("preload/images/titleEnter.xml"), ASSET_ROUTER.XML),
		ASSET.XML_TITLE_GIRLFRIEND: ASE(XMLResource("preload/images/gfDanceTitle.xml"), ASSET_ROUTER.XML),
		ASSET.XML_MAIN_MENU_ASSET: ASE(XMLResource("preload/images/FNF_main_menu_assets.xml"), ASSET_ROUTER.XML),
		ASSET.XML_STORY_MENU_CHARACTERS: ASE(XMLResource("preload/images/campaign_menu_UI_characters.xml"), ASSET_ROUTER.XML),
		ASSET.XML_STORY_MENU_UI: ASE(XMLResource("preload/images/campaign_menu_UI_assets.xml"), ASSET_ROUTER.XML),

		ASSET.IMG_STAGE_BACK: ImageResource("shared/images/stageback.png"),
		ASSET.IMG_STAGE_FRONT: ImageResource("shared/images/stagefront.png"),
		ASSET.IMG_STAGE_CURTAINS: ImageResource("shared/images/stagecurtains.png"),
		ASSET.IMG_HEALTH_BAR: ImageResource("shared/images/healthBar.png"),
		ASSET.IMG_READY: ImageResource("shared/images/ready.png"),
		ASSET.IMG_SET: ImageResource("shared/images/set.png"),
		ASSET.IMG_GO: ImageResource("shared/images/go.png"),
		ASSET.IMG_SICK: ImageResource("shared/images/sick.png", 0), # Throw all of these into the same
		ASSET.IMG_GOOD: ImageResource("shared/images/good.png", 0), # atlas, should improve combo sprite
		ASSET.IMG_BAD: ImageResource("shared/images/bad.png", 0),   # rendering somewhat
		ASSET.IMG_SHIT: ImageResource("shared/images/shit.png", 0),
		ASSET.IMG_NUM0: ImageResource("preload/images/num0.png", 0),
		ASSET.IMG_NUM1: ImageResource("preload/images/num1.png", 0),
		ASSET.IMG_NUM2: ImageResource("preload/images/num2.png", 0),
		ASSET.IMG_NUM3: ImageResource("preload/images/num3.png", 0),
		ASSET.IMG_NUM4: ImageResource("preload/images/num4.png", 0),
		ASSET.IMG_NUM5: ImageResource("preload/images/num5.png", 0),
		ASSET.IMG_NUM6: ImageResource("preload/images/num6.png", 0),
		ASSET.IMG_NUM7: ImageResource("preload/images/num7.png", 0),
		ASSET.IMG_NUM8: ImageResource("preload/images/num8.png", 0),
		ASSET.IMG_NUM9: ImageResource("preload/images/num9.png", 0),
		ASSET.IMG_NEWGROUNDS_LOGO: ImageResource("preload/images/newgrounds_logo.png"),
		ASSET.IMG_ICON_GRID: ASE(ImageResource("preload/images/iconGrid.png"), ASSET_ROUTER.ICON_GRID),
		ASSET.IMG_MENU_BG: ImageResource("preload/images/menuBG.png"),
		ASSET.IMG_MENU_DESAT: ImageResource("preload/images/menuDesat.png"),
		ASSET.IMG_MENU_BG_BLUE: ImageResource("preload/images/menuBGBlue.png"),

		ASSET.FONT_VCR: FontResource("fonts/vcr.ttf"),

		ASSET.SOUND_INTRO_3: OggResource("shared/sounds/intro3.ogg"),
		ASSET.SOUND_INTRO_2: OggResource("shared/sounds/intro2.ogg"),
		ASSET.SOUND_INTRO_1: OggResource("shared/sounds/intro1.ogg"),
		ASSET.SOUND_INTRO_GO: OggResource("shared/sounds/introGo.ogg"),
		ASSET.SOUND_LOSS: OggResource("shared/sounds/fnf_loss_sfx.ogg"),
		ASSET.SOUND_MENU_CONFIRM: OggResource("preload/sounds/confirmMenu.ogg"),
		ASSET.SOUND_MENU_SCROLL: OggResource("preload/sounds/scrollMenu.ogg"),

		ASSET.MUSIC_MENU: OggResource("preload/music/freakyMenu.ogg"),
		ASSET.MUSIC_GAME_OVER: OggResource("shared/music/gameOver.ogg"),
		ASSET.MUSIC_GAME_OVER_END: OggResource("shared/music/gameOverEnd.ogg"),

		ASSET.PATH_SONGS: PathResource("songs/"),
		ASSET.PATH_DATA: PathResource("preload/data/"),
		ASSET.PATH_WEEK_HEADERS: PathResource("preload/images/storymenu"),

		# NOTE: These are weird. Some sort of "router asset" that is fully dependant on a
		# router and whatever code calling `load_asset` passes in.
		# Maybe come up with something better than `None` here.`
		ASSET.WEEK_HEADERS: ASE(None, ASSET_ROUTER.WEEK_HEADERS),
		ASSET.SONGS: ASE(None, ASSET_ROUTER.SONGS),

		ASSET.TXT_INTRO_TEXT: TextResource("preload/data/introText.txt"),
	},
	{
		ASSET_ROUTER.ICON_GRID: IconGridRouter,
		ASSET_ROUTER.SONGS: SongRouter,
		ASSET_ROUTER.WEEK_HEADERS: WeekHeaderRouter,
		ASSET_ROUTER.XML: XMLRouter,
	})

	add_asset_system(_DEFAULT_ASSET_SYSTEM)
