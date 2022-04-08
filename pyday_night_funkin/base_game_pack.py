"""
Specifies the base game's assets and asset routers.
This is meant to be expanded into some sort of modding system,
but uuh, those plans are far in the future.
"""

from loguru import logger
import typing as t

from pyglet.math import Vec2
import schema

from pyday_night_funkin.core.asset_system import (
	ASSET, ASSET_ROUTER, AbstractAssetRouter, AssetSystem, AssetSystemEntry as ASE,
	OggResource, ImageResource, JSONResource, PathResource, TextResource, XMLResource,
	FontResource, register_assets, register_routers, add_asset_system, load_asset
)
from pyday_night_funkin.core.animation import FrameCollection
from pyday_night_funkin.character import Character, FlipIdleCharacter
from pyday_night_funkin.enums import ANIMATION_TAG, DIFFICULTY

if t.TYPE_CHECKING:
	from pathlib import Path
	from xml.etree.ElementTree import ElementTree
	from pyglet.image import Texture
	from pyglet.media import Source
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.core.types import Numeric


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
					# Keys I've seen that are ignored:
					# altAnim, typeOfSection.
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

	Will load a dict mapping animation prefixes to frame sequences.
	"""
	def get_route_funcs(self):
		return (self.route_xml, self.route_image, self.route_frames)

	def route_xml(self, xml_res: XMLResource) -> t.Tuple[XMLResource]:
		self.xml_res_path = xml_res.path
		return (xml_res,)

	def route_image(self, xml: "ElementTree") -> t.Tuple[ImageResource]:
		self.element_tree = xml
		return (ImageResource(self.xml_res_path.parent / xml.getroot().attrib["imagePath"]),)

	def route_frames(self, atlas_texture: "Texture") -> FrameCollection:
		texture_region_cache = {}
		frame_collection = FrameCollection()
		for sub_texture in self.element_tree.getroot():
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
		"XML_SKID_N_PUMP",
		"XML_MONSTER",
		"XML_HALLOWEEN_BG",
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
		"SOUND_THUNDER0",
		"SOUND_THUNDER1",
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
		ASSET.XML_SKID_N_PUMP: ASE(XMLResource("week2/images/spooky_kids_assets.xml"), ASSET_ROUTER.XML),
		ASSET.XML_MONSTER: ASE(XMLResource("week2/images/Monster_Assets.xml"), ASSET_ROUTER.XML),
		ASSET.XML_HALLOWEEN_BG: ASE(XMLResource("week2/images/halloween_bg.xml"), ASSET_ROUTER.XML),

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
		ASSET.SOUND_THUNDER0: OggResource("shared/sounds/thunder_1.ogg"),
		ASSET.SOUND_THUNDER1: OggResource("shared/sounds/thunder_2.ogg"),

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


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_BOYFRIEND)

		self.animation.add_by_prefix(
			"idle", "BF idle dance", 24, True, (-5, 0),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "BF NOTE LEFT0", 24, False, (12, -6),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_left", "BF NOTE LEFT MISS", 24, False, (12, 24),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "BF NOTE DOWN0", 24, False, (-10, -50),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_down", "BF NOTE DOWN MISS", 24, False, (-11, -19),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "BF NOTE UP0", 24, False, (-29, 27),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_up", "BF NOTE UP MISS", 24, False, (-29, 27),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "BF NOTE RIGHT0", 24, False, (-38, -7),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"miss_note_right", "BF NOTE RIGHT MISS", 24, False, (-30, 21),
			(ANIMATION_TAG.MISS,)
		)
		self.animation.add_by_prefix("scared", "BF idle shaking", 24, True, (-4, 0))
		self.animation.add_by_prefix(
			"hey", "BF HEY!!", 24, False, (7, 4), (ANIMATION_TAG.SPECIAL,)
		)
		self.animation.add_by_prefix(
			"game_over_ini", "BF dies", 24, False, (37, 11), (ANIMATION_TAG.GAME_OVER,)
		)
		self.animation.add_by_prefix(
			"game_over_loop", "BF Dead Loop", 24, True, (37, 5), (ANIMATION_TAG.GAME_OVER,)
		)
		self.animation.add_by_prefix(
			"game_over_confirm", "BF Dead confirm", 24, False, (37, 69),
			(ANIMATION_TAG.GAME_OVER,)
		)

	def update(self, dt: float) -> None:
		singing = self.animation.has_tag(ANIMATION_TAG.SING)
		missing = self.animation.has_tag(ANIMATION_TAG.MISS)
		if singing or missing:
			self.hold_timer += dt
		else:
			self.hold_timer = 0

		# If no keys are being held (dont_idle managed by the InGameScene) and the sing animation
		# has been running for a while now, move back to idling.
		if (
			self.hold_timer > self.scene.conductor.beat_duration * 0.001 and
			not self.dont_idle and singing
		):
			self.animation.play("idle")

		# If le epic fail animation ended, return to idling at a specific frame for some reason
		if missing and not self.animation.current.playing:
			self.animation.play("idle", True, 10)

		# Skip `Character.update` because it ruins everything
		# Admittedly this also ruins everything but you can blame the original code for that.
		super(Character, self).update(dt)

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu", "BF idle dance white", 24, True,
			tags = (ANIMATION_TAG.STORY_MENU,)
		)
		spr.animation.add_by_prefix(
			"story_menu_confirm", "BF HEY!!", 24, False,
			tags = (ANIMATION_TAG.STORY_MENU, ANIMATION_TAG.SPECIAL)
		)

	@staticmethod
	def get_story_menu_info() -> t.Tuple[t.Tuple["Numeric", "Numeric"], "Numeric", "Numeric"]:
		return ((100, 100), 1, .9)

	@staticmethod
	def get_string() -> str:
		return "bf"


class DaddyDearest(Character):

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_DADDY_DEAREST)

		self.animation.add_by_prefix(
			"idle", "Dad idle dance", 24, True, (0, 0), (ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "Dad Sing Note LEFT", 24, False, (-10, 10), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "Dad Sing Note DOWN", 24, False, (0, -30), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "Dad Sing Note UP", 24, False, (-6, 50), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "Dad Sing Note RIGHT", 24, False, (0, 27), (ANIMATION_TAG.SING,)
		)

	# Idk why but if the original game says so
	@staticmethod
	def get_hold_timeout() -> "Numeric":
		return 6.1

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"Dad idle dance BLACK LINE",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,),
		)

	@staticmethod
	def get_story_menu_info() -> t.Tuple[t.Tuple["Numeric", "Numeric"], "Numeric", "Numeric"]:
		return ((120, 200), 1, .5)

	@staticmethod
	def get_string() -> str:
		return "dad"


class Girlfriend(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_GIRLFRIEND)

		self.animation.add_by_prefix(
			"cheer", "GF Cheer", 24, False, tags=(ANIMATION_TAG.SPECIAL,)
		)
		self.animation.add_by_indices(
			"idle_left", "GF Dancing Beat", range(15), 24, False, (0, -9),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_indices(
			"idle_right", "GF Dancing Beat", range(15, 30), 24, False, (0, -9),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "GF left note", 24, False, (0, -19), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "GF Down Note", 24, False, (0, -20), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "GF Up Note", 24, False, (0, 4), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "GF Right Note", 24, False, (0, -20), (ANIMATION_TAG.SING,)
		)
		# Nice space at the end bro
		self.animation.add_by_prefix("scared", "GF FEAR ", 24, True, (-2, -17))

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"GF Dancing Beat WHITE",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,),
		)

	@staticmethod
	def get_story_menu_info() -> t.Tuple[t.Tuple["Numeric", "Numeric"], "Numeric", "Numeric"]:
		return ((100, 100), 1, .5)

	@staticmethod
	def get_string() -> str:
		return "gf"


class SkidNPump(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_SKID_N_PUMP)

		self.animation.add_by_prefix(
			"sing_note_up", "spooky UP NOTE", 24, False, (-20, 26),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "spooky DOWN note", 24, False, (-50, -130),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "note sing left", 24, False, (130, -10),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "spooky sing right", 24, False, (-130, -14),
			(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_indices(
			"idle_left", "spooky dance idle", [0, 2, 6], 12, False, (0, 0),
			(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_indices(
			"idle_right", "spooky dance idle", [8, 10, 12, 14], 12, False, (0, 0),
			(ANIMATION_TAG.IDLE,)
		)

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"spooky dance idle BLACK LINES",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,)
		)


class Monster(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_asset(ASSET.XML_MONSTER)

		# It's like they're trying to win a naming inconsistency award
		self.animation.add_by_prefix(
			"idle", "monster idle", 24, False, (0, 0), (ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "monster up note", 24, False, (-20, 50), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "monster down", 24, False, (-30, -40), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_left", "Monster left note", 24, False, (-30, 0), (ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "Monster Right note", 24, False, (-51, 0), (ANIMATION_TAG.SING,)
		)
