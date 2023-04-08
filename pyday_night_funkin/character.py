
from dataclasses import dataclass
import typing as t

from pyday_night_funkin.enums import ANIMATION_TAG
from pyday_night_funkin.core.pnf_sprite import PNFSprite

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import MusicBeatScene


class CharacterDataDict(t.TypedDict, total=False):
	hold_timeout: float
	story_menu_offset: t.Tuple[float, float]
	icon_name: t.Optional[str]


# This could be replaced with `Self`, but that's a 3.11 thing
CharacterDataT = t.TypeVar("CharacterDataT", bound="CharacterData")

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
