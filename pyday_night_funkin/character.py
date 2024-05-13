
# TODO: Ugly merge between a system that wants to express a very generic character and the
# standard base game with a sprite atlas + hardcoded offset text file in here.
# Fix eventually.

from __future__ import annotations

from dataclasses import dataclass
import re
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.asset_system import (
	AssetRequest, LoadingRequest, load_frames, load_text
)
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.enums import AnimationTag

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.scene import SceneLayer
	from pyday_night_funkin.core.types import Numeric
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.note import Note, NoteType
	from pyday_night_funkin.scenes import MusicBeatScene


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
		offset: t.Tuple[float, float] | None = None,
	) -> None:
		self.image = image
		self.animations = animations
		self.offset = offset


# class CharacterProtocol(t.Protocol):
# 	def dance(self) -> None: ...

# 	def get_focus_point(self) -> Vec2: ...

# 	@property
# 	def x(self) -> Numeric: ...
# 	@x.setter
# 	def x(self, _: Numeric) -> None: ...

# 	@property
# 	def y(self) -> Numeric: ...
# 	@y.setter
# 	def y(self, _: Numeric) -> None: ...

# 	@property
# 	def position(self) -> t.Tuple[Numeric, Numeric]: ...
# 	@position.setter
# 	def position(self, _: t.Tuple[Numeric, Numeric]): ...
	
# 	@property
# 	def width(self) -> Numeric: ...
# 	@property
# 	def height(self) -> Numeric: ...


class CharacterKernel(t.Generic[T]):
	"""
	A character kernel stores a lot of information to later
	instantiate a character. Wowee.
	"""

	def __init__(self, *args, **kwargs) -> None:
		self.args = args
		self.kwargs = kwargs

	def get_loading_hints(self, game: Game) -> LoadingRequest:
		return LoadingRequest({})

	def get_icon_name(self) -> str:
		raise NotImplementedError()

	def get_story_menu_data(self) -> StoryMenuCharacterData | None:
		raise NotImplementedError()

	def supports_direct_creation(self) -> bool:
		return False

	def create(self, scene: MusicBeatScene, *args, **kwargs) -> T:
		raise NotImplementedError()

	def create_direct(
		self,
		scene: MusicBeatScene,
		layer: SceneLayer | None,
		cameras: t.Iterable[Camera] | Camera | None,
		*args,
		**kwargs,
	) -> T:
		raise NotImplementedError()


class CharacterDataDict(t.TypedDict, total=False):
	type: t.Type["Character"]
	icon_name: str
	hold_timeout: float
	game_over_fallback: t.Hashable | None
	story_menu_data: StoryMenuCharacterData | None
	offset_id: str | None


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

	game_over_fallback: t.Hashable | None = None
	"""
	The id of a character that should instead be used in order to
	display the doomed variant on the game-over screen.
	This should be used if the character can be controlled by the
	player, but does not have `game_over` animations.
	If `None`, no such replacement will occur.
	"""

	story_menu_data: StoryMenuCharacterData | None = None
	"""
	How/what the character should display in the story menu.
	If `None`, will hide the accompanying sprite.
	"""
	# NOTE: Maybe refurbish this some more cause as it stands it's a pretty
	# primitive and unfinished solution. But good enough.

	offset_id: str | None = None
	"""
	Another ID for this character. Usually the one used by the base game
	(Week 7 / 0.2.8). Used to build paths to access related files such as
	offset files.
	Set to ``icon_name`` if not otherwise defined.
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

	def __init__(self, scene: MusicBeatScene, data: CharacterData, *args, **kwargs) -> None:
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
			not self.dont_idle and
			self.hold_timer > self._hold_timeout * self.scene.conductor.step_duration * 0.001
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

	def on_notes_hit(self, notes: t.Sequence[Note]) -> None:
		"""
		The character has hit the given notes.
		By default, plays an animation named ``sing_{x}`` where ``x`` is the
		last note's type name, lowercased.
		"""
		hit_note = notes[-1]
		self.hold_timer = 0.0
		self.animation.play(f"sing_{hit_note.type.name.lower()}", True)

	def on_notes_missed(self, notes: t.Sequence[Note]) -> None:
		"""
		Typically not called on non-player controlled characters.

		The character has missed the given notes by letting them pass the hit
		window.
		By default, plays an animation named ``miss_{x}`` where ``x`` is the
		last note's type name, lowercased.
		"""
		fail_note = notes[-1]
		self.animation.play(f"miss_{fail_note.type.name.lower()}", True)

	def on_misinput(self, note_type: NoteType) -> None:
		"""
		Typically not called on non-player controlled characters.

		The character has hit a note direction without any note being present.
		By default, plays an animation named ``miss_{x}`` where ``x`` is the
		note's type name, lowercased.
		"""
		self.animation.play(f"miss_{note_type.name.lower()}", True)

	def load_frames(self) -> None:
		"""
		Load this character's spritesheet via a call to ``load_frames``.
		Uses the ``sprite_sheet_name`` attribute of ``self.character_data``,
		prepending `"shared/images/characters/"` and appending the extension
		`".xml"`.
		"""
		ssn = self.character_data.sprite_sheet_name
		self.frames = load_frames(f"shared/images/characters/{ssn}.xml")

	def load_offsets(self, remapper: t.Dict[str, str] | None = None) -> None:
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
		offset_override: t.Tuple[float, float] | None = None,
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
		offset_override: t.Tuple[float, float] | None = None,
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

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self._dance_right = False

	def dance(self, force: bool = False) -> None:
		if force or self.should_dance():
			self._dance_right = not self._dance_right
			self.animation.play("idle_right" if self._dance_right else "idle_left")


class BaseGameCharacterKernel(CharacterKernel[Character]):
	def __init__(self, character_data: CharacterData, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self._char_data = character_data

	def get_loading_hints(self, game: Game) -> LoadingRequest:
		p = f"shared/images/characters/{self._char_data.sprite_sheet_name}.xml"
		p2 = f"shared/images/characters/{self._char_data.offset_id}Offsets.txt"

		lreq = LoadingRequest(
			{
				"frames": [AssetRequest((p,))],
				"text": [AssetRequest((p2,), may_fail=True)],
			}
		)
		if self._char_data.game_over_fallback is not None:
			lreq.add_subrequest(
				game.character_registry[self._char_data.game_over_fallback].get_loading_hints(game)
			)

		return lreq

	def get_icon_name(self) -> str:
		return self._char_data.icon_name

	def get_story_menu_data(self) -> StoryMenuCharacterData | None:
		return self._char_data.story_menu_data

	def supports_direct_creation(self) -> bool:
		return True

	def create(self, scene: MusicBeatScene, *args, **kwargs) -> Character:
		return self._char_data.type(scene, self._char_data, *args, **kwargs)

	def create_direct(self,
		scene: MusicBeatScene,
		layer: SceneLayer | None,
		cameras: t.Iterable[Camera] | Camera | None,
		*args,
		**kwargs,
	) -> Character:
		return scene.create_object(
			layer, cameras, self._char_data.type, scene, self._char_data, *args, **kwargs
		)
