
from dataclasses import dataclass
import re
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.asset_system import load_frames, load_text
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.enums import AnimationTag

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene

# This could be replaced with `Self`, but that's a 3.11 thing
CharacterDataT = t.TypeVar("CharacterDataT", bound="CharacterData")
T = t.TypeVar("T")


RE_OFFSETS_LINE = re.compile(r"^(.*)\s+(-?\d+)\s+(-?\d+)$")


# class PointDict(t.TypedDict):
# 	x: float
# 	y: float

# class AnimationDataDict(t.TypedDict):
# 	prefix: str
# 	tags: t.List[int]
# 	indices: t.List[int]
# 	fps: float
# 	offset: PointDict
# 	loop: bool

# NOTE: Man i'm gonna throw up; maybe figure out something nicer later(TM)
AnimationDataTuple = t.Union[
	t.Tuple[str],
	t.Tuple[str, float],
	t.Tuple[str, float, bool],
	t.Tuple[str, float, bool, t.Tuple[float, float]],
	t.Tuple[str, float, bool, t.Tuple[float, float], t.Sequence[t.Hashable]],
]
# yeah, this is a great idea.

class StoryMenuCharacterData:
	__slots__ = ("image", "animations", "offset")

	def __init__(
		self,
		image: str,
		animations: t.Sequence[AnimationDataTuple],
		offset: t.Optional[t.Tuple[float, float]] = None,
	) -> None:
		self.image = image
		self.animations = animations
		self.offset = offset


class CharacterDataDict(t.TypedDict, total=False):
	type: t.Type["Character"]
	icon_name: str
	hold_timeout: float
	game_over_fallback: t.Optional[t.Hashable]
	story_menu_data: t.Optional[StoryMenuCharacterData]
	offset_id: t.Optional[str]

@dataclass
class CharacterData:
	type: t.Type["Character"]
	"""
	This character's Python class/type.
	"""

	icon_name: str
	"""
	Name of this character's health icon.
	"""

	sprite_sheet_name: str
	"""
	Name of this character's sprite sheet name.
	"""

	hold_timeout: float = 4.0
	"""
	How many steps should pass until the character returns to their
	idle pose after singing. Default is `4.0`.
	"""

	game_over_fallback: t.Optional[t.Hashable] = None
	"""
	The id of a character that should instead be used in order to
	display the doomed variant on the game-over screen.
	This should be used if the character can be controlled by the
	player, but does not have `game_over` animations.
	If `None`, no such replacement will occur.
	"""

	story_menu_data: t.Optional[StoryMenuCharacterData] = None
	"""
	How/what the character should display in the story menu.
	If `None`, will hide the accompanying sprite.
	"""
	# NOTE: Maybe refurbish this some more cause as it stands it's a pretty
	# primitive and unfinished solution. But good enough.

	offset_id: t.Optional[str] = None
	"""
	The base game's ID for this character. Used to access other stuff
	in its assets such as offset files.
	"""

	# positioning: t.Optional[PositioningStrategy] = None

	def __post_init__(self) -> None:
		if self.offset_id is None:
			self.offset_id = self.icon_name

		# if self.positioning is None:
		# 	self.positioning = PositioningStrategy()


_ANIMATION_NAME_REMAP = {
	"danceLeft": "idle_left",
	"danceRight": "idle_right",
	"idleHair": "idle_hair",
	"singUP": "sing_up",
	"singDOWN": "sing_down",
	"singLEFT": "sing_left",
	"singRIGHT": "sing_right",
	"singUPmiss": "miss_up",
	"singDOWNmiss": "miss_down",
	"singLEFTmiss": "miss_left",
	"singRIGHTmiss": "miss_right",
	"firstDeath": "game_over_ini",
	"deathLoop": "game_over_loop",
	"deathConfirm": "game_over_end",
	"hairBlow": "hair_blow",
	"hairFall": "hair_fall",
}


class Character(PNFSprite):
	"""
	A beloved character that moves, sings and... well I guess that's
	about it. Holds some more information than a generic sprite which
	is related to the character via its `CharacterData` and
	additionally is coupled to a scene.
	"""

	def __init__(self, scene: "MusicBeatScene", data: CharacterData, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scene = scene
		self.character_data = data
		self._hold_timeout = data.hold_timeout
		self.hold_timer = 0.0
		self.animation_offsets: t.Dict[str, t.Tuple[float, float]] = {}
		"""
		Animation offsets for this character, used by `add_animation`.
		Load these using `load_offsets`.
		"""

		self.dont_idle: bool = False
		"""
		If set to `True`, the character won't idle/dance after their
		sing or miss animation is complete.
		"""

	def update(self, dt: float) -> None:
		super().update(dt)
		if (
			self.animation.has_tag(AnimationTag.SING) or
			self.animation.has_tag(AnimationTag.MISS)
		):
			self.hold_timer += dt

		if (
			self.hold_timer >= self._hold_timeout * self.scene.conductor.step_duration * 0.001 and
			not self.dont_idle
		):
			self.hold_timer = 0.0
			self.dance(True)

	def get_focus_point(self) -> Vec2:
		"""
		Returns an absolute coordinate a camera should be trained on
		to focus on this character.
		By default, returns `self.get_midpoint() + Vec2(150, -100)`.
		"""
		return self.get_midpoint() + Vec2(150.0, -100.0)

	def should_dance(self) -> bool:
		"""
		Determines whether the character should "dance", that is, play
		their idle animation.
		By default, returns `False` if the character's current
		animation is tagged `AnimationTag.SING` or `MISS`.
		"""
		return not (
			self.animation.has_tag(AnimationTag.SING) or
			self.animation.has_tag(AnimationTag.MISS)
		)

	def dance(self, force: bool = False) -> None:
		"""
		Makes the character play their idle animation.
		Unless `force` is set to `True`, this function calls into
		`should_dance` and will not do anything if it returns `False`.
		Subclassable for characters that alternate between dancing
		poses, by default just plays an animation called `idle`.
		"""
		if force or self.should_dance():
			self.animation.play("idle")

	def load_frames(self) -> None:
		"""
		Load this character's spritesheet via a call to ``load_frames``.
		Uses the ``sprite_sheet_name`` attribute of ``self.character_data``,
		prepending `"shared/images/characters/"` and appending the extension
		`".xml"`.
		"""
		ssn = self.character_data.sprite_sheet_name
		self.frames = load_frames(f"shared/images/characters/{ssn}.xml")

	def load_offsets(self, remapper: t.Optional[t.Dict[str, str]] = None) -> None:
		"""
		Attempts to load this character's offsets file into
		`self.animation_offsets`.
		Does nothing if the file can not be found.

		Since PNF's animation names deviate from the names in the
		offset files, by default this method will alter the keys of
		the offset map from stuff like `singRIGHTmiss` to `miss_right`.
		If this is not desired (or you want to have an influence on it),
		pass a different or empty dict as the `remapper` parameter.
		"""
		try:
			raw = load_text(
				f"shared/images/characters/{self.character_data.offset_id}Offsets.txt"
			)
		except FileNotFoundError:
			return

		remapper = _ANIMATION_NAME_REMAP if remapper is None else remapper
		res = {}
		for line in raw.split("\n"):
			if (match := RE_OFFSETS_LINE.match(line)) is not None:
				res[remapper.get(match[1], match[1])] = (float(match[2]), float(match[3]))

		self.animation_offsets = res

	def add_animation(
		self,
		name: str,
		prefix: str,
		fps: float = 24.0,
		loop: bool = False,
		tags: t.Sequence[AnimationTag] = (),
		offset_override: t.Optional[t.Tuple[float, float]] = None,
	) -> None:
		"""
		Convenience method that will call
		`self.animation.add_by_prefix` and create an animation with
		the given name from `prefix`.
		If not overridden, the offset is read from
		`self.animation_offsets`, so load them using `load_offsets`
		beforehand if necessary.
		"""
		offset = (
			self.animation_offsets.get(name, None) if offset_override is None else offset_override
		)
		self.animation.add_by_prefix(name, prefix, fps, loop, offset, tags)

	def add_indexed_animation(
		self,
		name: str,
		prefix: str,
		indices: t.Iterable[int],
		fps: float = 24.0,
		loop: bool = False,
		tags: t.Sequence[AnimationTag] = (),
		offset_override: t.Optional[t.Tuple[float, float]] = None,
	) -> None:
		"""
		Convenience method that will call
		`self.animation.add_by_indices` and create an animation from
		`prefix` and `indices`.
		If not overridden, the offset is read from
		`self.animation_offsets`, so load them using `load_offsets`
		beforehand if necessary.
		"""
		offset = (
			self.animation_offsets.get(name, None) if offset_override is None else offset_override
		)
		self.animation.add_by_indices(name, prefix, indices, fps, loop, offset, tags)


class FlipIdleCharacter(Character):
	"""
	Character that does not play the `idle` animation in their
	`dance` function but instead alternates between `idle_left`
	and `idle_right` each invocation.
	"""

	_dance_right = False

	def dance(self, force: bool = False) -> None:
		if force or self.should_dance():
			self._dance_right = not self._dance_right
			self.animation.play("idle_right" if self._dance_right else "idle_left")

# TODO: May be expanded into data-driven character setup by adding SimpleCharacterSetupData
# to the registry as an optional entry and populating from it accordingly, but i'll only care
# enough when the entire base game is in i think.

# class SimpleCharacterSetupDataDict(t.TypedDict, total=False):
# 	animations: t.Dict[str, AnimationDataDict]
# 	load_offsets: bool
