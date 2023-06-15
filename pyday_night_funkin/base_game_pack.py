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
	register_complex_asset_type,
)
from pyday_night_funkin.content_pack import ContentPack, LevelData, WeekData
from pyday_night_funkin.core.animation import FrameCollection
from pyday_night_funkin.character import (
	Character, CharacterData, FlipIdleCharacter, StoryMenuCharacterData
)
from pyday_night_funkin.enums import ANIMATION_TAG, DIFFICULTY

if t.TYPE_CHECKING:
	from xml.etree.ElementTree import ElementTree
	from pyglet.image import AbstractImage, Texture
	from pyglet.media import Source


class SeqValidator:
	"""
	Validator for the `schema` library that will only allow lists or
	tuples where each item matches the schema in the corresponding
	blueprint. Validates into a tuple.
	"""

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


def _load_character_icon(character: str) -> t.Tuple["Texture", "Texture"]:
	"""
	Loads an icon grid image and a character string into health icons.

	Returns two-element tuple of 150px x 150px textures, a character's
	default and losing icon.
	"""

	icon_texture = load_image(f"preload/images/icons/icon-{character}.png")

	if icon_texture.width != 300 or icon_texture.height != 150:
		raise ValueError("Icon texture has an invalid shape: Must be 300x150!")

	return (
		icon_texture.get_region(  0, 0, 150, 150).get_texture(),
		icon_texture.get_region(150, 0, 150, 150).get_texture(),
	)

load_character_icon = register_complex_asset_type(
	"character_icon", lambda c: c, _load_character_icon
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

load_song = register_complex_asset_type("song", lambda sn, opt: (sn, opt), _load_song_plain)


def load_week_header(name: str) -> "Texture":
	return load_image(os.path.join(load_pyobj("PATH_WEEK_HEADERS"), name))

def _load_frames_plain(path: str) -> FrameCollection:
	"""
	Loads animation frames from path.
	Will load a `FrameCollection`, which can directly be set to a
	sprite's `frames` attribute.
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
		self.load_offsets()

		self.add_animation("idle", "BF idle dance", tags=(ANIMATION_TAG.IDLE,))
		self.add_animation("sing_left", "BF NOTE LEFT0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_left", "BF NOTE LEFT MISS", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("sing_down", "BF NOTE DOWN0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_down", "BF NOTE DOWN MISS", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("sing_up", "BF NOTE UP0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_up", "BF NOTE UP MISS", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("sing_right", "BF NOTE RIGHT0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_right", "BF NOTE RIGHT MISS", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("scared", "BF idle shaking", loop=True)
		self.add_animation("hey", "BF HEY!!", tags=(ANIMATION_TAG.SPECIAL,))
		self.add_animation("game_over_ini", "BF dies")
		self.add_animation("game_over_loop", "BF Dead Loop", loop=True)
		self.add_animation("game_over_end", "BF Dead confirm")

		self.animation.play("idle")

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
		# TODO: Maybe, juuust maybe class OpponentCharacter(Character) and move it out
		# there good god
		super(Character, self).update(dt)

	def get_focus_point(self) -> Vec2:
		return self.get_midpoint() + Vec2(-100.0, -100.0)


class Girlfriend(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scroll_factor = (0.95, 0.95)

		self.frames = load_frames("shared/images/characters/GF_assets.xml")
		self.load_offsets()

		self.add_animation("cheer", "GF Cheer", tags=(ANIMATION_TAG.SPECIAL,))
		self.add_indexed_animation(
			"idle_left", "GF Dancing Beat", range(15), tags=(ANIMATION_TAG.IDLE,)
		)
		self.add_indexed_animation(
			"idle_right", "GF Dancing Beat", range(15, 30), tags=(ANIMATION_TAG.IDLE,)
		)
		self.add_animation("sing_left", "GF left note", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_down", "GF Down Note", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_right", "GF Right Note", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_up", "GF Up Note", tags=(ANIMATION_TAG.SING,))
		# Nice space at the end bro
		self.add_animation("scared", "GF FEAR ")
		self.add_indexed_animation(
			"hair_blow", "GF Dancing Beat Hair blowing", range(4), 24, True, (ANIMATION_TAG.HAIR,)
		)
		self.add_indexed_animation(
			"hair_fall", "GF Dancing Beat Hair Landing", range(12), tags=(ANIMATION_TAG.HAIR,)
		)

		self.animation.play("idle_right")

	def should_dance(self) -> bool:
		return not self.animation.has_tag(ANIMATION_TAG.HAIR) and super().should_dance()

	def update(self, dt: float) -> None:
		super().update(dt)
		if (ca := self.animation.current) is None:
			return

		if ANIMATION_TAG.HAIR in ca.tags and not ca.playing:
			self._dance_right = False
			self.animation.play("idle_right")


class DaddyDearest(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/DADDY_DEAREST.xml")
		self.load_offsets()

		self.add_animation("idle", "Dad idle dance", tags=(ANIMATION_TAG.IDLE,))
		self.add_animation("sing_left", "Dad Sing Note LEFT", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_down", "Dad Sing Note DOWN", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_up", "Dad Sing Note UP", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_right", "Dad Sing Note RIGHT", tags=(ANIMATION_TAG.SING,))

		self.animation.play("idle")


class SkidNPump(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/spooky_kids_assets.xml")
		self.load_offsets()

		self.add_animation("sing_up", "spooky UP NOTE", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_down", "spooky DOWN note", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_left", "note sing left", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_right", "spooky sing right", tags=(ANIMATION_TAG.SING,))

		self.add_indexed_animation(
			"idle_left", "spooky dance idle", (0, 2, 6), 12, tags=(ANIMATION_TAG.IDLE,)
		)
		self.add_indexed_animation(
			"idle_right", "spooky dance idle", (8, 10, 12, 14), 12, tags=(ANIMATION_TAG.IDLE,)
		)

		self.animation.play("idle_right")


class Monster(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/Monster_Assets.xml")
		self.load_offsets()

		# It's like they're trying to win a naming inconsistency award
		self.add_animation("idle", "monster idle", tags=(ANIMATION_TAG.IDLE,))
		self.add_animation("sing_up", "monster up note", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_down", "monster down", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_left", "Monster left note", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_right", "Monster Right note", tags=(ANIMATION_TAG.SING,))

		self.animation.play("idle")

class Pico(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/Pico_FNF_assetss.xml")
		self.load_offsets()

		self.add_animation("idle", "Pico Idle Dance", tags=(ANIMATION_TAG.IDLE,))
		self.add_animation("sing_up", "pico Up note0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_down", "Pico Down Note0", tags=(ANIMATION_TAG.SING,))
		# my god why
		self.add_animation("sing_left", "Pico Note Right0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_right", "Pico NOTE LEFT0", tags=(ANIMATION_TAG.SING,))

		self.flip_x = True

		self.animation.play("idle")


# mother of christ this is disgusting but hey whatever. Thanks:
# https://stackoverflow.com/questions/56980077/how-to-type-python-mixin-with-superclass-calls
class HairLoopMixin(Character if t.TYPE_CHECKING else object):
	def update(self, dt: float) -> None:
		super().update(dt)
		if (
			not self.animation.current.playing and
			ANIMATION_TAG.SING not in self.animation.current.tags
		):
			self.animation.play("idle_hair")


class BoyfriendCar(HairLoopMixin, Boyfriend):
	def __init__(self, *args, **kwargs) -> None:
		# Skip Boyfriend.__init__
		super(Boyfriend, self).__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/bfCar.xml")
		self.load_offsets()

		self.add_animation("idle", "BF idle dance", tags=(ANIMATION_TAG.IDLE,))
		self.add_animation("sing_up", "BF NOTE UP0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_up", "BF NOTE UP MISS0", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("sing_left", "BF NOTE LEFT0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_left", "BF NOTE LEFT MISS0", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("sing_right", "BF NOTE RIGHT0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_right", "BF NOTE RIGHT MISS0", tags=(ANIMATION_TAG.MISS,))
		self.add_animation("sing_down", "BF NOTE DOWN0", tags=(ANIMATION_TAG.SING,))
		self.add_animation("miss_down", "BF NOTE DOWN MISS0", tags=(ANIMATION_TAG.MISS,))
		self.add_indexed_animation("idle_hair", "BF idle dance", (10, 11, 12, 13))

		self.animation.play("idle")


class GirlfriendCar(HairLoopMixin, FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/gfCar.xml")
		self.load_offsets()

		self.add_indexed_animation("idle_left", "GF Dancing Beat Hair blowing CAR", range(15))
		self.add_indexed_animation(
			"idle_right", "GF Dancing Beat Hair blowing CAR", range(15, 30)
		)
		self.add_indexed_animation(
			"idle_hair", "GF Dancing Beat Hair blowing CAR", (10, 11, 12, 25, 26, 27)
		)

		self.animation.play("idle_right")


class MommyMearest(HairLoopMixin, Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.frames = load_frames("shared/images/characters/momCar.xml")
		self.load_offsets()
		self.add_animation("idle", "Mom Idle", tags=(ANIMATION_TAG.IDLE,))
		self.add_animation("sing_up", "Mom Up Pose", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_down", "MOM DOWN POSE", tags=(ANIMATION_TAG.SING,))
		self.add_animation("sing_left", "Mom Left Pose", tags=(ANIMATION_TAG.SING,))
		# well done
		self.add_animation("sing_right", "Mom Pose Left", tags=(ANIMATION_TAG.SING,))
		self.add_indexed_animation("idle_hair", "Mom Idle", (10, 11, 12, 13))

		self.animation.play("idle")


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


class BaseGameAssetRouter(AssetRouter):
	def __init__(self,):
		self._iro = ImageResourceOptions(0)

		# Throw most UI sprites into the same atlas, should improve rendering of it
		# somewhat
		_entry = AssetRouterEntry(None, ImageResourceOptions(0))
		super().__init__({
			"shared/images/sick.png":         _entry,
			"shared/images/good.png":         _entry,
			"shared/images/bad.png":          _entry,
			"shared/images/shit.png":         _entry,
			"shared/images/healthBar.png":    _entry,
			"preload/images/NOTE_assets.png": _entry,
			"preload/images/num0.png":        _entry,
			"preload/images/num1.png":        _entry,
			"preload/images/num2.png":        _entry,
			"preload/images/num3.png":        _entry,
			"preload/images/num4.png":        _entry,
			"preload/images/num5.png":        _entry,
			"preload/images/num6.png":        _entry,
			"preload/images/num7.png":        _entry,
			"preload/images/num8.png":        _entry,
			"preload/images/num9.png":        _entry,
			"preload/images/main_menu.xml":
				AssetRouterEntry(post_load_processor=main_menu_path_post_load_hacker),
		})

	def has_asset(
		self, path: str, asset_type_name: str, options: t.Optional[ResourceOptions]
	) -> t.Optional[t.Tuple[str, t.Optional[ResourceOptions], t.Optional[PostLoadProcessor]]]:
		sup = super().has_asset(path, asset_type_name, options)
		if sup is not None:
			return sup

		# Throw icons into the same atlas as combo sprites. This should work out nicely.
		if path.startswith("preload/images/icons/"):
			return (path, self._iro, None)

		return None


def load() -> ContentPack:
	"""
	Loads everything required to run the base game into the asset
	system and returns the base game's content pack.
	"""

	add_asset_router(BaseGameAssetRouter())
	add_complex_asset_router(BaseGameComplexAssetRouter())
	add_pyobj_router(PyobjRouter({
		"PATH_WEEK_HEADERS": "preload/images/storymenu/",
		"PATH_DATA": "preload/data/",
		"PATH_SONGS": "songs/",
	}))

	# Deferred import, yuck! Quickest way to fix the circular import rn,
	# could possibly split the levels and characters into a basegame submodule later.
	from pyday_night_funkin.stages import (
		TutorialStage,
		Week1Stage, BopeeboStage, FreshStage,
		Week2Stage, MonsterStage,
		Week3Stage,
		Week4Stage,
	)

	# Characters do not have IDs like gf; gf-pixel; gf-car; bf; bf-pixel; bf-car; mom; mom-car
	# etc. anymore, where behavior is massively built around pre- and suffixes.
	# They still have IDs. These are the keys given in this dict. Their class follows as well as a
	# CharacterData dict, which may be enhanced by a concrete character class if it so desires.
	# On initialization, characters receive the CharacterData and can then go do whatever
	# with it.

	# Could add class generation for more customization, MOOOOORE;
	# But man, we'd be going off the deep end with that.

	bf_smcd = StoryMenuCharacterData(
		"preload/images/campaign_menu_UI_characters.xml",
		(
			("BF idle dance white", 24, True),
			("BF HEY!!", 24, False),
		)
	)
	gf_smcd = StoryMenuCharacterData(
		"preload/images/campaign_menu_UI_characters.xml",
		(("GF Dancing Beat WHITE", 24, True),),
	)
	dad_smcd = StoryMenuCharacterData(
		"preload/images/campaign_menu_UI_characters.xml",
		(("Dad idle dance BLACK LINE", 24, True),),
		(120.0, 200.0),
	)
	snp_smcd = StoryMenuCharacterData(
		"preload/images/campaign_menu_UI_characters.xml",
		(("spooky dance idle BLACK LINES", 24, True),),
	)
	pico_smcd = StoryMenuCharacterData(
		"preload/images/campaign_menu_UI_characters.xml",
		(("Pico Idle Dance", 24, True),),
	)
	mom_smcd = StoryMenuCharacterData(
		"preload/images/campaign_menu_UI_characters.xml",
		(("Mom Idle BLACK LINES", 24, True),),
		(100.0, 200.0),
	)

	return ContentPack(
		pack_id = "_pnf_base",
		characters = {
			"boyfriend":      CharacterData(Boyfriend, "bf", story_menu_data=bf_smcd),
			"girlfriend":     CharacterData(Girlfriend, "gf", story_menu_data=gf_smcd),
			"daddy_dearest":  CharacterData(DaddyDearest, "dad", 6.1, story_menu_data=dad_smcd),
			"skid_n_pump":    CharacterData(SkidNPump, "spooky", story_menu_data=snp_smcd),
			"monster":        CharacterData(Monster, "monster"),
			"pico":           CharacterData(Pico, "pico", story_menu_data=pico_smcd),
			"boyfriend_car":  CharacterData(
				BoyfriendCar, "bf", game_over_fallback="boyfriend", offset_id="bf-car"
			),
			"girlfriend_car": CharacterData(GirlfriendCar, "gf", offset_id="gf-car"),
			"mommy_mearest":  CharacterData(
				MommyMearest, "mom", story_menu_data=mom_smcd, offset_id="mom-car"
			),
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
						"fresh", "Fresh", FreshStage, "boyfriend", "girlfriend", "daddy_dearest"
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
					LevelData("pico", "Pico", Week3Stage, "boyfriend", "girlfriend", "pico"),
					LevelData("philly", "Philly", Week3Stage, "boyfriend", "girlfriend", "pico"),
					LevelData("blammed", "Blammed", Week3Stage, "boyfriend", "girlfriend", "pico"),
				),
				"week3.png",
			),
			WeekData(
				"MOMMY MUST MURDER",
				("mommy_mearest", "boyfriend", "girlfriend"),
				(
					LevelData(
						"satin-panties",
						"Satin Panties",
						Week4Stage,
						"boyfriend_car",
						"girlfriend_car",
						"mommy_mearest",
					),
					LevelData(
						"high", "High", Week4Stage, "boyfriend_car", "girlfriend_car", "mommy_mearest"
					),
					LevelData(
						"milf",
						"MILF",
						Week4Stage,
						"boyfriend_car",
						"girlfriend_car",
						"mommy_mearest",
					),
				),
				"week4.png",
			),
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
