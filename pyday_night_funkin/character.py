
from dataclasses import dataclass
import re
import typing as t

from pyday_night_funkin.core.asset_system import load_text
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.enums import ANIMATION_TAG

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


# This could be replaced with `Self`, but that's a 3.11 thing
CharacterDataT = t.TypeVar("CharacterDataT", bound="CharacterData")

class CharacterDataDict(t.TypedDict, total=False):
	hold_timeout: float
	story_menu_offset: t.Tuple[float, float]
	icon_name: t.Optional[str]


RE_OFFSETS_LINE = re.compile(r"^(.*)\s+(-?\d+)\s+(-?\d+)$")


@dataclass
class CharacterData:
	hold_timeout: float
	"""
	Hold timeout. Default is `4.0`.
	"""

	story_menu_offset: t.Tuple[float, float]
	"""
	Offset of the sprite in the story menu.
	Default is `(100.0, 100.0)`.
	"""

	icon_name: t.Optional[str]
	"""
	Name of this character's health icon.
	"""

	def update(self: CharacterDataT, updater: CharacterDataDict) -> CharacterDataT:
		"""
		Updates the CharacterData from the given dict and then
		returns itself.
		"""
		self.hold_timeout = updater.get("hold_timeout", self.hold_timeout)
		self.story_menu_offset = updater.get("story_menu_offset", self.story_menu_offset)
		self.icon_name = updater.get("icon_name", self.icon_name)
		return self


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
	is related to the character via `get_character_data`.
	"""

	def __init__(self, scene: "MusicBeatScene", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.scene = scene
		self.hold_timer = 0.0
		self.character_data = self.get_character_data()
		self._hold_timeout = self.character_data.hold_timeout
		self.dont_idle: bool = False
		"""
		If set to `True`, the character won't idle/dance after their
		sing or miss animation is complete.
		"""

	def update(self, dt: float) -> None:
		super().update(dt)
		if (
			self.animation.has_tag(ANIMATION_TAG.SING) or
			self.animation.has_tag(ANIMATION_TAG.MISS)
		):
			self.hold_timer += dt

		if (
			self.hold_timer >= self._hold_timeout * self.scene.conductor.step_duration * 0.001 and
			not self.dont_idle
		):
			self.hold_timer = 0.0
			self.dance()

	def dance(self) -> None:
		"""
		Makes the character play their idle animation.
		Subclassable for characters that alternate between dancing
		poses, by default just plays an animation called `idle`.
		"""
		self.animation.play("idle")

	@classmethod
	def get_character_data(cls) -> CharacterData:
		return CharacterData(
			hold_timeout = 4.0,
			story_menu_offset = (100.0, 100.0),
			icon_name = "face",
		)

	@staticmethod
	def initialize_story_menu_sprite(spr: PNFSprite) -> None:
		"""
		Initializes a sprite with story menu animations.
		It is expected that an animation called `story_menu` will be
		added. Also, `story_menu_confirm` is required for every story
		character appearing in the center (usually just bf.)
		"""
		raise NotImplementedError("Subclass this.")

	def load_offsets(self, id_: str, remapper: t.Optional[t.Dict[str, str]] = None) -> None:
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
				f"shared/images/characters/{id_}Offsets.txt"
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
		tags: t.Sequence[ANIMATION_TAG] = (),
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
		tags: t.Sequence[ANIMATION_TAG] = (),
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

	def dance(self) -> None:
		self._dance_right = not self._dance_right
		self.animation.play("idle_right" if self._dance_right else "idle_left")
