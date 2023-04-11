"""
Specifies the base game's assets and asset routers.
This is meant to be expanded into some sort of modding system,
but uuh, those plans are far in the future.
"""

import os
from pathlib import Path
import re
from loguru import logger
import typing as t

from pyglet.math import Vec2
from schema import Schema, SchemaError, And, Or, Optional

from pyday_night_funkin.core.asset_system import (
	AssetRouter, ComplexAssetRouter, PyobjRouter, AssetRouterEntry,
	ImageResourceOptions, PostLoadProcessor, ResourceOptions, SoundResourceOptions,
	add_asset_router, add_complex_asset_router, add_pyobj_router,
	load_image, load_json, load_pyobj, load_sound, load_xml,
	register_complex_asset_type, register_optionless_asset_type,
)
from pyday_night_funkin.content_pack import ContentPack, LevelData, WeekData
from pyday_night_funkin.core.animation import FrameCollection
from pyday_night_funkin.character import Character, FlipIdleCharacter
from pyday_night_funkin.enums import ANIMATION_TAG, DIFFICULTY

if t.TYPE_CHECKING:
	from xml.etree.ElementTree import ElementTree
	from pyglet.image import AbstractImage, Texture
	from pyglet.media import Source
	from pyday_night_funkin.character import CharacterData
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class SeqValidator:
	def __init__(self, *types: t.Any) -> None:
		self.schemas = tuple(x if isinstance(x, Schema) else Schema(x) for x in types)

	def validate(self, v: t.Any) -> t.Tuple:
		if not isinstance(v, (list, tuple)):
			raise SchemaError("Value is not a tuple or list.")
		if len(v) != len(self.schemas):
			raise SchemaError(f"Stored sequence of unexpected length: {len(v)}")

		return tuple(s.validate(x) for s, x in zip(self.schemas, v))


SONG_SCHEMA = Schema(
	{
		"song": {
			"song": str,
			"notes": [And(
				{
					"lengthInSteps": int,
					Optional("bpm"): Or(int, float),
					Optional("changeBPM"): bool,
					"mustHitSection": bool,
					"sectionNotes": [SeqValidator(Or(int, float), int, Or(int, float))],
					# Keys I've seen that are ignored:
					# altAnim, typeOfSection.
					Optional(str): object,
				},
				lambda d: ("changeBPM" in d) <= ("bpm" in d),
			)],
			"bpm": Or(int, float),
			"needsVoices": bool,
			"player1": str,
			"player2": str,
			"speed": Or(int, float),
			# Keys I've seen that are ignored:
			# sections, sectionLengths, validScore.
			Optional(str): object,
		},
	},
	# Sometimes a very scuffed version of ["song"] also exists at the
	# root level. how you end up with that spaghetti bs and sleep calmly
	# knowing it's out in the world is beyond me
	ignore_extra_keys = True,
)


_HEALTH_ICON_MAP = {
	"bf":                ((   0,   0), ( 150,   0)),
	"spooky":            (( 300,   0), ( 450,   0)),
	"pico":              (( 600,   0), ( 750,   0)),
	"mom":               (( 900,   0), (1050,   0)),
	"tankman":           ((1200,   0), (1350,   0)),
	"face":              ((   0, 150), ( 150, 150)),
	"dad":               (( 300, 150), ( 450, 150)),
	"bf-old":            (( 600, 150), ( 750, 150)),
	"gf":                (( 900, 150), ( 900, 150)),
	"parents-christmas": ((1050, 150), (1200, 150)),
	"monster":           ((1350, 150), (   0, 300)),
	"bf-pixel":          (( 150, 300), ( 150, 300)),
	"senpai":            (( 300, 300), ( 300, 300)),
	"spirit":            (( 450, 300), ( 450, 300)),
}

def load_health_icon(character: str) -> t.Tuple["Texture", "Texture"]:
	"""
	Loads an icon grid image and a character string into health icons.

	Returns two-element tuple of 150px x 150px textures, a character's
	default and losing icon.
	"""

	icon_texture = load_image("preload/images/iconGrid.png")
	if icon_texture.width < 1500 or icon_texture.height < 900:
		raise ValueError("Icon grid has invalid shape!")

	return tuple(
		icon_texture.get_region(x, icon_texture.height - 150 - y, 150, 150).get_texture()
		for x, y in _HEALTH_ICON_MAP[character]
	)



class SongResourceOptions(ResourceOptions):
	def __init__(
		self,
		difficulty: t.Optional["DIFFICULTY"] = None,
		inst_opt: t.Optional[SoundResourceOptions] = None,
		voice_opt: t.Optional[SoundResourceOptions] = None,
	) -> None:
		self.difficulty = DIFFICULTY.NORMAL if difficulty is None else difficulty
		self.inst_opt = SoundResourceOptions() if inst_opt is None else inst_opt
		self.voice_opt = SoundResourceOptions() if voice_opt is None else voice_opt

	def __eq__(self, o: object) -> bool:
		if not isinstance(o, SongResourceOptions):
			return NotImplemented
		return (
			self.inst_opt == o.inst_opt and
			self.voice_opt == o.voice_opt and
			self.difficulty is o.difficulty
		)

	def __hash__(self) -> int:
		return hash((self.difficulty, self.inst_opt, self.voice_opt))


def _load_song_build_cache_key(song_name: str, options: SongResourceOptions):
	return (song_name, options)

def _load_song_plain(
	song_name: str,
	options: SongResourceOptions,
) -> t.Tuple["Source", t.Optional["Source"], t.Dict]:
	"""
	Loads song data.
	Will load a three-tuple of (Source, Source | None, dict); being
	the instrumental source, the voice source and the song data.
	"""
	chart_file = f"{song_name}{options.difficulty.to_song_json_suffix()}.json"
	chart_path = os.path.join(load_pyobj("PATH_DATA"), song_name, chart_file)
	raw_chart = load_json(chart_path, cache=False)
	chart = SONG_SCHEMA.validate(raw_chart)["song"]

	song_dir = os.path.join(load_pyobj("PATH_SONGS"), song_name)
	inst = load_sound(os.path.join(song_dir, "Inst.ogg"), options.inst_opt, False)
	voic = None
	if chart["needsVoices"]:
		voic = load_sound(os.path.join(song_dir, "Voices.ogg"), options.voice_opt, False)

	return (inst, voic, chart)

load_song = register_complex_asset_type("song", _load_song_build_cache_key, _load_song_plain)

def load_week_header(name: str) -> "Texture":
	return load_image(os.path.join(load_pyobj("PATH_WEEK_HEADERS"), name))

def _load_frames_plain(path: str) -> FrameCollection:
	"""
	Loads animation frames from path.

	Will load a dict mapping animation prefixes to frame sequences.
	"""
	# Do not cache the xml, only needed for creating the FrameCollection once, really.
	xml = load_xml(path, cache=False)
	atlas_texture = load_image(str(Path(path).parent / xml.getroot().attrib["imagePath"]), False)
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

load_frames = register_complex_asset_type("frames", lambda path: path, _load_frames_plain)


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/BOYFRIEND.xml")

		self.animation.add_by_prefix(
			"idle", "BF idle dance", 24, False, (-5, 0),
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

	@classmethod
	def get_character_data(cls) -> "CharacterData":
		return super().get_character_data().update({"icon_name": "bf"})

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


class DaddyDearest(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/DADDY_DEAREST.xml")

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

	@classmethod
	def get_character_data(cls) -> "CharacterData":
		return super().get_character_data().update({
			"hold_timeout": 6.1,
			"story_menu_offset": (120.0, 200.0),
			"icon_name": "dad",
		})

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"Dad idle dance BLACK LINE",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,),
		)


class Girlfriend(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/GF_assets.xml")

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
		self.animation.add_by_indices(
			"hair_blow", "GF Dancing Beat Hair blowing", [*range(4)], 24, True,
			(45, -8), (ANIMATION_TAG.HAIR,)
		)
		self.animation.add_by_indices(
			"hair_fall", "GF Dancing Beat Hair Landing", [*range(12)], 24, False,
			(0, -9), (ANIMATION_TAG.HAIR,)
		)

	@classmethod
	def get_character_data(cls) -> "CharacterData":
		return super().get_character_data().update({"icon_name": "gf"})

	def dance(self) -> None:
		if not self.animation.has_tag(ANIMATION_TAG.HAIR):
			super().dance()

	def update(self, dt: float) -> None:
		super().update(dt)
		if (ca := self.animation.current) is None:
			return

		if ANIMATION_TAG.HAIR in ca.tags and not ca.playing:
			self.animation.play("idle_right")

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu",
			"GF Dancing Beat WHITE",
			fps = 24,
			loop = True,
			tags = (ANIMATION_TAG.STORY_MENU,),
		)


class SkidNPump(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/spooky_kids_assets.xml")

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

	@classmethod
	def get_character_data(cls) -> "CharacterData":
		return super().get_character_data().update({"icon_name": "spooky"})

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

		self.frames = load_frames("shared/images/characters/Monster_Assets.xml")

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

	@classmethod
	def get_character_data(cls) -> "CharacterData":
		return super().get_character_data().update({"icon_name": "monster"})


class Pico(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/Pico_FNF_assetss.xml")

		self.animation.add_by_prefix(
			"idle", "Pico Idle Dance", offset=(0, 0), tags=(ANIMATION_TAG.IDLE,)
		)
		self.animation.add_by_prefix(
			"sing_note_up", "pico Up note0", offset=(-29, 27), tags=(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_down", "Pico Down Note0", offset=(200, -70), tags=(ANIMATION_TAG.SING,)
		)
		# MY GOD WHY
		self.animation.add_by_prefix(
			"sing_note_left", "Pico Note Right0", offset=(65, 9), tags=(ANIMATION_TAG.SING,)
		)
		self.animation.add_by_prefix(
			"sing_note_right", "Pico NOTE LEFT0", offset=(-68, -7), tags=(ANIMATION_TAG.SING,)
		)

		self.flip_x = True

	@classmethod
	def get_character_data(cls) -> "CharacterData":
		return super().get_character_data().update({"icon_name": "pico"})

	@staticmethod
	def initialize_story_menu_sprite(spr: "PNFSprite") -> None:
		spr.animation.add_by_prefix(
			"story_menu", "Pico Idle Dance", 24, True,
			tags = (ANIMATION_TAG.STORY_MENU,)
		)



# HACK: This manipulates the cached note asset frame collection, since notes have
# botched offsets that are fixed with a hardcoded center->subtract in the main loop.
# Nobody wants that, so we hack in some offsets right here.
# Both were probably found by trial-and-error, so good enough (TM)
def note_arrow_frame_collection_post_load_hacker(fcol: FrameCollection) -> FrameCollection:
	for frame in fcol.frames:
		if re.search(r"confirm instance \d+$", frame.name) is not None:
			frame.offset -= Vec2(39, 39)
	return fcol


# HACK: This manipulates the main menu's xml's imagePath to point to `main_menu.png`,
# as from the week 7 update it pointed to the old file name `FNF_main_menu_assets.png`.
# Honestly i don't know how to handle this. HaxeFlixel simply ignores this the imagePath
# and always loads the same two files with their extensions modified, but lol lmao.
# I'll be damned if i don't show off my shitty overengineered asset system.
def main_menu_path_post_load_hacker(et: "ElementTree") -> "ElementTree":
	et.getroot().set("imagePath", "main_menu.png")
	return et


class BaseGameComplexAssetRouter(ComplexAssetRouter):
	def has_asset(
		self, asset_type_name: str, *args: t.Any, **kwargs: t.Any
	) -> t.Optional[
		t.Tuple[t.Tuple[t.Any, ...], t.Dict[str, t.Any], t.Optional[PostLoadProcessor]]
	]:
		if (
			asset_type_name == "frames" and
			len(args) == 1 and
			args[0] == "preload/images/NOTE_assets.xml"
		):
			return (args, kwargs, note_arrow_frame_collection_post_load_hacker)

		return None


def load() -> ContentPack:
	"""
	Loads everything required to run the base game into the asset
	system and returns the base game's content pack.
	"""

	# Throw all of these into the same atlas, should improve combo sprite
	# rendering somewhat
	_iro = AssetRouterEntry(None, ImageResourceOptions(0))
	asset_system_map = {
		"shared/images/sick.png":  _iro,
		"shared/images/good.png":  _iro,
		"shared/images/bad.png":   _iro,
		"shared/images/shit.png":  _iro,
		"preload/images/num0.png": _iro,
		"preload/images/num1.png": _iro,
		"preload/images/num2.png": _iro,
		"preload/images/num3.png": _iro,
		"preload/images/num4.png": _iro,
		"preload/images/num5.png": _iro,
		"preload/images/num6.png": _iro,
		"preload/images/num7.png": _iro,
		"preload/images/num8.png": _iro,
		"preload/images/num9.png": _iro,
		"preload/images/main_menu.xml":
			AssetRouterEntry(post_load_processor=main_menu_path_post_load_hacker),
	}

	add_asset_router(AssetRouter(asset_system_map))
	add_complex_asset_router(BaseGameComplexAssetRouter())
	add_pyobj_router(PyobjRouter({
		"PATH_WEEK_HEADERS": "preload/images/storymenu/",
		"PATH_DATA": "preload/data/",
		"PATH_SONGS": "songs/",
	}))

	# Deferred import, yuck! Quickest way to fix the circular import rn,
	# could possibly split the levels and characters into a basegame submodule later.
	from pyday_night_funkin.stages import (
		TutorialStage, Week1Stage, BopeeboStage, Week2Stage, MonsterStage, Week3Stage
	)

	return ContentPack(
		pack_id = "_pnf_base",
		characters = {
			"boyfriend":     Boyfriend,
			"girlfriend":    Girlfriend,
			"daddy_dearest": DaddyDearest,
			"skid_n_pump":   SkidNPump,
			"monster":       Monster,
			"pico":          Pico,
		},
		weeks = (
			WeekData(
				"",
				("daddy_dearest", "boyfriend", "girlfriend"),
				(
					LevelData(
						"tutorial", "Tutorial", TutorialStage, "boyfriend", None, "girlfriend"
					),
				),
				"week0.png",
			),
			WeekData(
				"DADDY DEAREST",
				("daddy_dearest", "boyfriend", "girlfriend"),
				(
					LevelData(
						"bopeebo", "Bopeebo", BopeeboStage, "boyfriend", "girlfriend", "daddy_dearest"
					),
					LevelData(
						"fresh", "Fresh", Week1Stage, "boyfriend", "girlfriend", "daddy_dearest"
					),
					LevelData(
						"dadbattle", "Dadbattle", Week1Stage, "boyfriend", "girlfriend", "daddy_dearest"
					),
				),
				"week1.png",
			),
			WeekData(
				"SPOOKY MONTH",
				("skid_n_pump", "boyfriend", "girlfriend"),
				(
					LevelData(
						"spookeez", "Spookeez", Week2Stage, "boyfriend", "girlfriend", "skid_n_pump"
					),
					LevelData(
						"south", "South", Week2Stage, "boyfriend", "girlfriend", "skid_n_pump"
					),
					LevelData(
						"monster", "Monster", MonsterStage, "boyfriend", "girlfriend", "monster"
					),
				),
				"week2.png",
			),
			WeekData(
				"PICO",
				("pico", "boyfriend", "girlfriend"),
				(
					LevelData(
						"pico", "Pico", Week3Stage, "boyfriend", "girlfriend", "pico"
					),
					LevelData(
						"philly", "Philly", Week3Stage, "boyfriend", "girlfriend", "pico"
					),
					LevelData(
						"blammed", "Blammed", Week3Stage, "boyfriend", "girlfriend", "pico"
					),
				),
				"week3.png",
			),
			# WeekData(
			# 	"MOMMY MUST MURDER",
			# 	("mom", "boyfriend", "girlfriend"),
			# 	(
			# 		LevelData(
			# 			"satin-panties", "Satin Panties", Week4Stage, "boyfriend-car", "mom"
			# 		),
			# 		LevelData(
			# 			"high", "High", Week4Stage, "boyfriend-car", "girlfriend-car", "mom"
			# 		),
			# 		LevelData(
			# 			"milf", "M.I.L.F.", Week4Stage, "boyfriend-car", "girlfriend-car", "mom"
			# 		),
			# 	),
			# 	"week4.png",
			# ),
			# WeekData(
			# 	"RED SNOW",
			# 	("parents-christmas", "boyfriend", "girlfriend"),
			# 	(
			# 		LevelData(),
			# 		LevelData(),
			# 		LevelData(),
			# 	),
			# 	"week5.png",
			# ),
			# WeekData(
			# 	"hating simulator ft. moawling",
			# 	("senpai", "boyfriend", "girlfriend"),
			# 	(
			# 		LevelData(),
			# 		LevelData(),
			# 		LevelData(),
			# 	),
			# 	"week6.png",
			# ),
			# WeekData(
			# 	"TANKMAN",
			# 	("tankman", "boyfriend", "girlfriend"),
			# 	(
			# 		LevelData(),
			# 		LevelData(),
			# 		LevelData(),
			# 	),
			# 	"week7.png",
			# ),
		),
	)
