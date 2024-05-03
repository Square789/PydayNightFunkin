"""
Specifies the base game's assets and asset routers.

Contains a good chunk of FNF logic implemented in various `load_` and
`fetch_` methods.
"""

from pathlib import Path
import re
import typing as t

from pyglet.math import Vec2
from schema import Schema, SchemaError, And, Or, Optional

from pyday_night_funkin.core.asset_system import (
	AssetProvider, AssetRouter, AssetRouterEntry, LibrarySpecPattern, JSONAssetProvider,
	load_image, load_json, load_pyobj, load_sound,
)
from pyday_night_funkin.content_pack import ContentPack, LevelData, WeekData
from pyday_night_funkin.core.animation import FrameCollection
from pyday_night_funkin.character import (
	Character, CharacterData, FlipIdleCharacter, StoryMenuCharacterData
)
from pyday_night_funkin.enums import AnimationTag, Difficulty

if t.TYPE_CHECKING:
	from xml.etree.ElementTree import ElementTree
	from pyglet.image import Texture, TextureRegion
	from pyglet.media import Source
	from pyday_night_funkin.main_game import Game


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


def fetch_character_icons(character: str) -> t.Tuple["TextureRegion", "TextureRegion"]:
	"""
	Loads a 300x150 image of two character icons and returns its two
	health icons as TextureRegions.
	Images must be in ``preload/images/icons`` in a file named
	``icon-{character}.png``

	Returns two-element tuple of 150px x 150px textures, a character's
	default and losing icon.
	"""

	icon_texture = load_image(f"preload/images/icons/icon-{character}.png")

	if icon_texture.width != 300 or icon_texture.height != 150:
		raise ValueError("Icon texture has an invalid shape: Must be 300x150!")

	return (icon_texture.get_region(0, 0, 150, 150), icon_texture.get_region(150, 0, 150, 150))


def fetch_week_header(name: str) -> "Texture":
	"""
	Retrieves the week header image of the given name.
	The directory this is loaded from is dependant on the
	`"PATH_WEEK_HEADERS"` exposed by the current asset router stack.
	"""
	return load_image(load_pyobj("PATH_WEEK_HEADERS") / name)


def fetch_song(
	song_name: str,
	difficulty: "Difficulty",
) -> t.Tuple["Source", t.Optional["Source"], t.Dict]:
	"""
	Loads song data for a standard FNF song.
	Will load a three-tuple of (Source, Source | None, dict); being
	the instrumental source, the voice source and the song data.
	"""
	data = load_song_data(song_name, difficulty)
	song_dir = load_pyobj("PATH_SONGS") / song_name
	inst = load_sound(song_dir / "Inst.ogg")
	voic = None
	if data["needsVoices"]:
		voic = load_sound(song_dir / "Voices.ogg")

	return (inst, voic, data)


class SongDataAssetProvider(AssetProvider):
	def load(self, song_name: str, difficulty: "Difficulty") -> t.Dict:
		chart_path = (
			load_pyobj("PATH_DATA") /
			song_name /
			f"{song_name}{difficulty.to_song_json_suffix()}.json"
		)
		raw = load_json(chart_path, cache=False)

		return SONG_SCHEMA.validate(raw)["song"]

	def create_cache_key(self, song_name: str, difficulty: "Difficulty") -> t.Hashable:
		return (song_name, difficulty)

	def get_estimated_asset_size(self, item) -> int:
		return JSONAssetProvider.get_estimated_asset_size(self, item)


_g_load_song_data = None


def load_song_data(song_name: str, difficulty: "Difficulty", *, cache: bool = True) -> t.Dict:
	"""
	Loads and validates the standard FNF chart of the given
	difficutly for the given song.
	The directory this is loaded from is dependant on the
	`"PATH_DATA"` exposed by the current asset router stack.
	"""
	if _g_load_song_data is None:
		raise RuntimeError("blegh")
	return _g_load_song_data(song_name, difficulty, cache=cache)


class Boyfriend(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.load_frames()
		self.load_offsets()

		self.add_animation("idle", "BF idle dance", tags=(AnimationTag.IDLE,))
		self.add_animation("sing_left", "BF NOTE LEFT0", tags=(AnimationTag.SING,))
		self.add_animation("miss_left", "BF NOTE LEFT MISS", tags=(AnimationTag.MISS,))
		self.add_animation("sing_down", "BF NOTE DOWN0", tags=(AnimationTag.SING,))
		self.add_animation("miss_down", "BF NOTE DOWN MISS", tags=(AnimationTag.MISS,))
		self.add_animation("sing_up", "BF NOTE UP0", tags=(AnimationTag.SING,))
		self.add_animation("miss_up", "BF NOTE UP MISS", tags=(AnimationTag.MISS,))
		self.add_animation("sing_right", "BF NOTE RIGHT0", tags=(AnimationTag.SING,))
		self.add_animation("miss_right", "BF NOTE RIGHT MISS", tags=(AnimationTag.MISS,))
		self.add_animation("scared", "BF idle shaking", loop=True)
		self.add_animation("hey", "BF HEY!!", tags=(AnimationTag.SPECIAL,))
		self.add_animation("game_over_ini", "BF dies")
		self.add_animation("game_over_loop", "BF Dead Loop", loop=True)
		self.add_animation("game_over_end", "BF Dead confirm")

		self.animation.play("idle")

	def update(self, dt: float) -> None:
		singing = self.animation.has_tag(AnimationTag.SING)
		missing = self.animation.has_tag(AnimationTag.MISS)
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

		self.load_frames()
		self.load_offsets()

		self.add_animation("cheer", "GF Cheer", tags=(AnimationTag.SPECIAL,))
		self.add_indexed_animation(
			"idle_left", "GF Dancing Beat", range(15), tags=(AnimationTag.IDLE,)
		)
		self.add_indexed_animation(
			"idle_right", "GF Dancing Beat", range(15, 30), tags=(AnimationTag.IDLE,)
		)
		self.add_animation("sing_left", "GF left note", tags=(AnimationTag.SING,))
		self.add_animation("sing_down", "GF Down Note", tags=(AnimationTag.SING,))
		self.add_animation("sing_right", "GF Right Note", tags=(AnimationTag.SING,))
		self.add_animation("sing_up", "GF Up Note", tags=(AnimationTag.SING,))
		self.add_indexed_animation("sad", "gf sad", range(13), loop=True)
		# Nice space at the end bro
		self.add_animation("scared", "GF FEAR ")
		self.add_indexed_animation(
			"hair_blow", "GF Dancing Beat Hair blowing", range(4), 24, True, (AnimationTag.HAIR,)
		)
		self.add_indexed_animation(
			"hair_fall", "GF Dancing Beat Hair Landing", range(12), tags=(AnimationTag.HAIR,)
		)

		self.animation.play("idle_right")

	def should_dance(self) -> bool:
		return not self.animation.has_tag(AnimationTag.HAIR) and super().should_dance()

	def update(self, dt: float) -> None:
		super().update(dt)
		if (ca := self.animation.current) is None:
			return

		if AnimationTag.HAIR in ca.tags and not ca.playing:
			self._dance_right = False
			self.animation.play("idle_right")


class DaddyDearest(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.load_frames()
		self.load_offsets()

		self.add_animation("idle", "Dad idle dance", tags=(AnimationTag.IDLE,))
		self.add_animation("sing_left", "Dad Sing Note LEFT", tags=(AnimationTag.SING,))
		self.add_animation("sing_down", "Dad Sing Note DOWN", tags=(AnimationTag.SING,))
		self.add_animation("sing_up", "Dad Sing Note UP", tags=(AnimationTag.SING,))
		self.add_animation("sing_right", "Dad Sing Note RIGHT", tags=(AnimationTag.SING,))

		self.animation.play("idle")


class SkidNPump(FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.load_frames()
		self.load_offsets()

		self.add_animation("sing_up", "spooky UP NOTE", tags=(AnimationTag.SING,))
		self.add_animation("sing_down", "spooky DOWN note", tags=(AnimationTag.SING,))
		self.add_animation("sing_left", "note sing left", tags=(AnimationTag.SING,))
		self.add_animation("sing_right", "spooky sing right", tags=(AnimationTag.SING,))

		self.add_indexed_animation(
			"idle_left", "spooky dance idle", (0, 2, 6), 12, tags=(AnimationTag.IDLE,)
		)
		self.add_indexed_animation(
			"idle_right", "spooky dance idle", (8, 10, 12, 14), 12, tags=(AnimationTag.IDLE,)
		)

		self.animation.play("idle_right")


class Monster(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.load_frames()
		self.load_offsets()

		# It's like they're trying to win a naming inconsistency award
		self.add_animation("idle", "monster idle", tags=(AnimationTag.IDLE,))
		self.add_animation("sing_up", "monster up note", tags=(AnimationTag.SING,))
		self.add_animation("sing_down", "monster down", tags=(AnimationTag.SING,))
		self.add_animation("sing_left", "Monster left note", tags=(AnimationTag.SING,))
		self.add_animation("sing_right", "Monster Right note", tags=(AnimationTag.SING,))

		self.animation.play("idle")

class Pico(Character):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.load_frames()
		self.load_offsets()

		self.add_animation("idle", "Pico Idle Dance", tags=(AnimationTag.IDLE,))
		self.add_animation("sing_up", "pico Up note0", tags=(AnimationTag.SING,))
		self.add_animation("sing_down", "Pico Down Note0", tags=(AnimationTag.SING,))
		# my god why
		self.add_animation("sing_left", "Pico Note Right0", tags=(AnimationTag.SING,))
		self.add_animation("sing_right", "Pico NOTE LEFT0", tags=(AnimationTag.SING,))

		self.flip_x = True

		self.animation.play("idle")


# mother of christ this is disgusting but hey whatever. Thanks:
# https://stackoverflow.com/questions/56980077/how-to-type-python-mixin-with-superclass-calls
class HairLoopMixin(Character if t.TYPE_CHECKING else object):
	def update(self, dt: float) -> None:
		super().update(dt)
		if (
			not self.animation.current.playing and
			AnimationTag.SING not in self.animation.current.tags
		):
			self.animation.play("idle_hair")


class BoyfriendCar(HairLoopMixin, Boyfriend):
	def __init__(self, *args, **kwargs) -> None:
		# Skip Boyfriend.__init__
		super(Boyfriend, self).__init__(*args, **kwargs)

		self.load_frames()
		self.load_offsets()

		self.add_animation("idle", "BF idle dance", tags=(AnimationTag.IDLE,))
		self.add_animation("sing_up", "BF NOTE UP0", tags=(AnimationTag.SING,))
		self.add_animation("miss_up", "BF NOTE UP MISS0", tags=(AnimationTag.MISS,))
		self.add_animation("sing_left", "BF NOTE LEFT0", tags=(AnimationTag.SING,))
		self.add_animation("miss_left", "BF NOTE LEFT MISS0", tags=(AnimationTag.MISS,))
		self.add_animation("sing_right", "BF NOTE RIGHT0", tags=(AnimationTag.SING,))
		self.add_animation("miss_right", "BF NOTE RIGHT MISS0", tags=(AnimationTag.MISS,))
		self.add_animation("sing_down", "BF NOTE DOWN0", tags=(AnimationTag.SING,))
		self.add_animation("miss_down", "BF NOTE DOWN MISS0", tags=(AnimationTag.MISS,))
		self.add_indexed_animation("idle_hair", "BF idle dance", (10, 11, 12, 13))

		self.animation.play("idle")


class GirlfriendCar(HairLoopMixin, FlipIdleCharacter):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scroll_factor = (0.95, 0.95)

		self.load_frames()
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

		self.load_frames()
		self.load_offsets()

		self.add_animation("idle", "Mom Idle", tags=(AnimationTag.IDLE,))
		self.add_animation("sing_up", "Mom Up Pose", tags=(AnimationTag.SING,))
		self.add_animation("sing_down", "MOM DOWN POSE", tags=(AnimationTag.SING,))
		self.add_animation("sing_left", "Mom Left Pose", tags=(AnimationTag.SING,))
		# well done
		self.add_animation("sing_right", "Mom Pose Left", tags=(AnimationTag.SING,))
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



class BaseGameAssetRouter(AssetRouter):
	def __init__(self, asset_directory: t.Union[Path, str]) -> None:
		# Throw most UI sprites into the same atlas, should improve rendering of it
		# somewhat
		_entry = AssetRouterEntry(options={"atlas_hint": 0})

		super().__init__(
			asset_directory,
			{},
			{
				"image": {
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

					# Throw icons into the same atlas as combo sprites.
					"//re:preload/images/icons/.*":   _entry,
				},
				"frames": {
					"preload/images/NOTE_assets.xml": AssetRouterEntry(
						post_load_processor = note_arrow_frame_collection_post_load_hacker,
					),
				},
				"xml": {
					"preload/images/main_menu.xml":
						AssetRouterEntry(post_load_processor=main_menu_path_post_load_hacker),
				},
				"sound": {
					# Install a short sound for loop testing
					# "preload/music/freakyMenu.ogg": AssetRouterEntry("shared/sounds/thunder_2.ogg"),
				},
			},
			{
				"PATH_WEEK_HEADERS": Path("preload/images/storymenu/"),
				"PATH_DATA":         Path("preload/data/"),
				"PATH_SONGS":        Path("songs/"),
			},
			{
				"shared": (
					LibrarySpecPattern("shared/images/shit.png"),
					LibrarySpecPattern("shared/images/bad.png"),
					LibrarySpecPattern("shared/images/good.png"),
					LibrarySpecPattern("shared/images/sick.png"),
					LibrarySpecPattern("shared/images/healthBar.png"),
					LibrarySpecPattern("shared/images/ready.png"),
					LibrarySpecPattern("shared/images/set.png"),
					LibrarySpecPattern("shared/images/go.png"),
					LibrarySpecPattern("shared/sounds/intro?.ogg"),
					LibrarySpecPattern("preload/images/num?.png"),
				),
				"week1": (
					LibrarySpecPattern("shared/images/stageback.png"),
					LibrarySpecPattern("shared/images/stagecurtains.png"),
					LibrarySpecPattern("shared/images/stagefront.png"),
				),
				"week2": (LibrarySpecPattern("week2", exclude=("*.fla", "*.mp3")),),
				"week3": (LibrarySpecPattern("week3", exclude=("*.fla", "*.mp3")),),
				"week4": (LibrarySpecPattern("week4", exclude=("*.fla", "*.mp3")),),
				# "week5": (LibrarySpecPattern("week5", exclude=("*.fla", "*.mp3")),),
				# "week6": (LibrarySpecPattern("week6", exclude=("*.fla", "*.mp3")),),
				# "week7": (LibrarySpecPattern("week7", exclude=("*.fla", "*.mp3")),),
			},
		)


def load(game: "Game") -> ContentPack:
	"""
	Loads everything required to run the base game into the asset
	system and returns the base game's content pack.
	"""
	global _g_load_song_data

	asset_dir = Path.cwd() / "assets"

	_g_load_song_data = game.assets.register_complex_asset_provider(
		"_pnf_song_data", SongDataAssetProvider
	)
	game.assets.set_default_asset_directory(asset_dir)
	game.assets.add_asset_router(BaseGameAssetRouter(asset_dir))

	# Deferred import, yuck! Quickest way to fix the circular import rn,
	# could possibly split the levels and characters into a basegame submodule later.
	from pyday_night_funkin.stages import (
		TutorialStage,
		Week1Stage, BopeeboStage, FreshStage,
		Week2Stage, MonsterStage,
		Week3Stage,
		Week4Stage, MILFStage,
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

	week1_libs = ("shared", "week1")
	week2_libs = ("shared", "week2")
	week3_libs = ("shared", "week3")
	week4_libs = ("shared", "week4")
	# week5_libs = ("shared", "week5")
	# week6_libs = ("shared", "week6")
	# week7_libs = ("shared", "week7")

	return ContentPack(
		pack_id = "_pnf_base",
		characters = {
			"boyfriend":      CharacterData(Boyfriend, "bf", "BOYFRIEND", story_menu_data=bf_smcd),
			"girlfriend":     CharacterData(
				Girlfriend, "gf", "GF_assets", story_menu_data=gf_smcd
			),
			"daddy_dearest":  CharacterData(
				DaddyDearest, "dad", "DADDY_DEAREST", 6.1, story_menu_data=dad_smcd
			),
			"skid_n_pump":    CharacterData(
				SkidNPump, "spooky", "spooky_kids_assets", story_menu_data=snp_smcd
			),
			"monster":        CharacterData(Monster, "monster", "Monster_Assets"),
			"pico":           CharacterData(
				Pico, "pico", "Pico_FNF_assetss", story_menu_data=pico_smcd
			),
			"boyfriend_car":  CharacterData(
				BoyfriendCar, "bf", "bfCar", game_over_fallback="boyfriend", offset_id="bf-car"
			),
			"girlfriend_car": CharacterData(GirlfriendCar, "gf", "gfCar", offset_id="gf-car"),
			"mommy_mearest":  CharacterData(
				MommyMearest, "mom", "momCar", story_menu_data=mom_smcd, offset_id="mom-car"
			),
		},
		weeks = (
			WeekData(
				"",
				("daddy_dearest", "boyfriend", "girlfriend"),
				(
					LevelData(
						"tutorial",
						"Tutorial",
						TutorialStage,
						"boyfriend",
						None,
						"girlfriend",
						week1_libs,
					),
				),
				"week0.png",
			),
			WeekData(
				"DADDY DEAREST",
				("daddy_dearest", "boyfriend", "girlfriend"),
				(
					LevelData(
						"bopeebo",
						"Bopeebo",
						BopeeboStage,
						"boyfriend",
						"girlfriend",
						"daddy_dearest",
						week1_libs,
					),
					LevelData(
						"fresh",
						"Fresh",
						FreshStage,
						"boyfriend",
						"girlfriend",
						"daddy_dearest",
						week1_libs,
					),
					LevelData(
						"dadbattle",
						"Dadbattle",
						Week1Stage,
						"boyfriend",
						"girlfriend",
						"daddy_dearest",
						week1_libs,
					),
				),
				"week1.png",
			),
			WeekData(
				"SPOOKY MONTH",
				("skid_n_pump", "boyfriend", "girlfriend"),
				(
					LevelData(
						"spookeez",
						"Spookeez",
						Week2Stage,
						"boyfriend",
						"girlfriend",
						"skid_n_pump",
						week2_libs,
					),
					LevelData(
						"south",
						"South",
						Week2Stage,
						"boyfriend",
						"girlfriend",
						"skid_n_pump",
						week2_libs,
					),
					LevelData(
						"monster",
						"Monster",
						MonsterStage,
						"boyfriend",
						"girlfriend",
						"monster",
						week2_libs,
					),
				),
				"week2.png",
			),
			WeekData(
				"PICO",
				("pico", "boyfriend", "girlfriend"),
				(
					LevelData(
						"pico",
						"Pico",
						Week3Stage,
						"boyfriend",
						"girlfriend",
						"pico",
						week3_libs,
					),
					LevelData(
						"philly",
						"Philly",
						Week3Stage,
						"boyfriend",
						"girlfriend",
						"pico",
						week3_libs,
					),
					LevelData(
						"blammed",
						"Blammed",
						Week3Stage,
						"boyfriend",
						"girlfriend",
						"pico",
						week3_libs,
					),
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
						week4_libs,
					),
					LevelData(
						"high",
						"High",
						Week4Stage,
						"boyfriend_car",
						"girlfriend_car",
						"mommy_mearest",
						week4_libs,
					),
					LevelData(
						"milf",
						"MILF",
						MILFStage,
						"boyfriend_car",
						"girlfriend_car",
						"mommy_mearest",
						week4_libs,
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
