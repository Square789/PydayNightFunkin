
import math
import typing as t

from pyday_night_funkin import constants as CNST
from pyday_night_funkin.base_game_pack import load_frames
from pyday_night_funkin.core.animation import AnimationController
from pyday_night_funkin.core.utils import ListWindow
from pyday_night_funkin.enums import Control
from pyday_night_funkin.note import Note, NoteType, SustainStage

if t.TYPE_CHECKING:
	from pyglet.image import Texture
	from pyday_night_funkin.scenes import InGameScene

# NOTE: Value extracted from width of first frame in the note spritesheet.
_MAGIC_ARROW_OFFSET = 157 * .7


class AbstractNoteHandler:
	"""
	Base class for a note handler. A class that receives input and is
	responsible for spawning, moving and deleting notes.
	"""
	def __init__(self, game_scene: "InGameScene", note_layer: str, note_camera: str) -> None:
		raise NotImplementedError("Abstract class.")

	def feed_song_data(self, song_data) -> None:
		raise NotImplementedError("Abstract class.")

	def update(self, dt: float) -> t.Any:
		raise NotImplementedError("Abstract class.")


class NoteHandler(AbstractNoteHandler):
	"""
	Class responsible for spawning, moving and deleting notes as well
	as processing key input.
	"""

	NOTE_TO_CONTROL_MAP = {
		NoteType.LEFT: Control.LEFT,
		NoteType.DOWN: Control.DOWN,
		NoteType.UP: Control.UP,
		NoteType.RIGHT: Control.RIGHT,
	}

	def __init__(self, game_scene: "InGameScene", note_layer: str, note_camera: str) -> None:
		self.note_layer = note_layer
		self.note_camera = note_camera

		self.game_scene = game_scene

		self.scroll_speed = game_scene.game.save_data.config.scroll_speed
		self.safe_window = game_scene.game.save_data.config.safe_window

		self.notes: t.List[Note] = []
		self.notes_visible = ListWindow(self.notes, 0, 0)
		"""Notes that are on screen and have a sprite registered.
		(May not actually be visible since they may have been played)"""

		self.notes_playable = ListWindow(self.notes, 0, 0)
		"""Notes that are playable based solely on their song position.
		(These may actually have been played or - for absurd scroll
		speeds - be invisible.)"""

		note_assets = load_frames("preload/images/NOTE_assets.xml")
		def single_frame(pref: str) -> "Texture":
			return note_assets.collect_ordered_by_prefix(pref)[0].texture

		# this is the worst naming of anything i have ever seen
		self.note_sprites = {
			SustainStage.NONE: {
				NoteType.LEFT: single_frame("purple instance 1"),
				NoteType.DOWN: single_frame("blue instance 1"),
				NoteType.UP: single_frame("green instance 1"),
				NoteType.RIGHT: single_frame("red instance 1"),
			},
			SustainStage.TRAIL: {
				NoteType.LEFT: single_frame("purple hold piece instance 1"),
				NoteType.DOWN: single_frame("blue hold piece instance 1"),
				NoteType.UP: single_frame("green hold piece instance 1"),
				NoteType.RIGHT: single_frame("red hold piece instance 1"),
			},
			SustainStage.END: {
				NoteType.LEFT: single_frame("pruple end hold instance 1"), # :^|
				NoteType.DOWN: single_frame("blue hold end instance 1"),
				NoteType.UP: single_frame("green hold end instance 1"),
				NoteType.RIGHT: single_frame("red hold end instance 1"),
			},
		}

	def feed_song_data(self, song_data) -> None:
		"""
		Supply the NoteHandler with song data which it needs to
		generate the notes. This should happen before any calls
		to `update`!
		"""
		self.scroll_speed *= song_data["speed"]
		for section in song_data["notes"]:
			for time_, type_, sustain in section["sectionNotes"]:
				singer = int(section["mustHitSection"]) # 0: opponent, 1: bf
				if type_ >= len(NoteType): # Note is sung by other character
					type_ %= len(NoteType)
					singer ^= 1
				type_ = NoteType(type_)

				self.notes.append(Note(singer, time_, type_, sustain, SustainStage.NONE))
				trail_notes = math.ceil(sustain / self.game_scene.conductor.step_duration)
				for i in range(trail_notes): # 0 and effectless for non-sustain notes.
					self.notes.append(Note(
						singer,
						time_ + (self.game_scene.conductor.step_duration * (i + 1)),
						type_,
						sustain,
						SustainStage.END if i == trail_notes - 1 else SustainStage.TRAIL,
					))
		self.notes.sort()

	def update(
		self,
		pressed: t.Dict[NoteType, bool],
	) -> t.Tuple[t.List[Note], t.List[Note], t.Dict[NoteType, t.Optional[Note]]]:
		"""
		Update the note handler, causing it to move all onscreen notes
		and handle hit/missed notes.
		`pressed` should be a dict containing each held down type the
		handler needs (see `NOTE_TO_CONTROL_MAP`) in its keys and
		whether each note type's control was "just pressed" in its
		values.
		This update method returns a three-value tuple:
			- Notes the opponent hit
			- Notes the player missed
			- A dict with the same keys as the passed `pressed` dict,
				where each value is either the note that was hit or,
				if the player missed, None.
		"""
		# TODO: Could create methods on the ListWindow to eliminate
		# "grow, update-shrink" code duplication

		song_pos = self.game_scene.conductor.song_position

		# Pixels a note traverses in a millisecond
		speed = 0.45 * self.scroll_speed
		note_vis_window_time = (CNST.GAME_HEIGHT - CNST.STATIC_ARROW_Y) / speed

		# Checks for notes that entered the visibility window, creates their sprites.
		while (
			self.notes_visible.end < len(self.notes) and
			self.notes[self.notes_visible.end].time - song_pos <= note_vis_window_time
		):
			cur_note = self.notes[self.notes_visible.end]
			self.notes_visible.end += 1
			if cur_note.rating is not None:
				# Played before becoming visible?
				# Hints at absurd scroll speed but i guess it's a possibility
				continue

			sprite = self.game_scene.create_object(
				self.note_layer,
				self.note_camera,
				x = (
					50 +
					cur_note.type.get_order() * CNST.NOTE_WIDTH +
					(CNST.GAME_WIDTH // 2) * cur_note.singer
				),
				y = -2000,
				image = self.note_sprites[cur_note.sustain_stage][cur_note.type],
			)
			sprite.set_scale_and_repos(.7)
			if cur_note.sustain_stage is not SustainStage.NONE:
				sprite.opacity = 153
				sprite.x += (_MAGIC_ARROW_OFFSET - sprite.width) / 2
				if cur_note.sustain_stage is SustainStage.TRAIL:
					sprite.set_scale_y_and_repos(
						self.game_scene.conductor.step_duration * (1/30) * speed
					)
			cur_note.sprite = sprite

		# Updates and shrinks visible notes window, moves notes, deletes off-screen ones.
		deletion_bound = 0
		for i, note in enumerate(self.notes_visible):
			note_y = CNST.STATIC_ARROW_Y - (song_pos - note.time) * speed
			if note_y < -note.sprite.height:
				deletion_bound = max(deletion_bound, i + 1)
			elif note.rating is None:
				note.sprite.y = note_y
		for idx in range(self.notes_visible.start, self.notes_visible.start + deletion_bound):
			note = self.notes[idx]
			self.game_scene.remove(note.sprite)
			note.sprite = None
			self.notes_visible.start += 1

		# Finds new playable notes
		while (
			self.notes_playable.end < len(self.notes) and
			self.notes[self.notes_playable.end].is_playable(song_pos, self.safe_window)
		):
			self.notes_playable.end += 1

		# Updates playable notes and shrinks playable notes window by removing missed notes.
		missed_notes = []
		opponent_hit_notes = []
		deletion_bound = 0
		for i, note in enumerate(self.notes_playable):
			prev_hitstate = note.rating
			note.check_playability(song_pos, self.safe_window)
			if prev_hitstate != note.rating and note.singer == 0:
				opponent_hit_notes.append(note)
				if note.sprite is not None:
					note.sprite.visible = False
			if not note.is_playable(song_pos, self.safe_window):
				deletion_bound = max(deletion_bound, i + 1)
		for idx in range(self.notes_playable.start, self.notes_playable.start + deletion_bound):
			note = self.notes[idx]
			if note.rating is None and note.singer == 1:
				missed_notes.append(note) # BUT HER AIM IS GETTING BETTER
			self.notes_playable.start += 1

		# Input processing here
		res_hit_map = {type_: None for type_ in pressed}
		for note in self.notes_playable:
			if (
				note.playable and
				# note type's control is down
				note.type in res_hit_map and
				# no other note was already encountered
				res_hit_map[note.type] is None and
				# Was either just pressed or is a sustain note
				(pressed[note.type] or note.sustain_stage is not SustainStage.NONE)
			):
				# Congrats, note hit
				res_hit_map[note.type] = note
				note.on_hit(song_pos, self.safe_window)
				if note.sprite is not None:
					note.sprite.visible = False

		return opponent_hit_notes, missed_notes, res_hit_map
