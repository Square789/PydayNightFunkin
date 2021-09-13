
from itertools import islice
import math
import typing as t

from pyday_night_funkin.asset_system import ASSETS
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.note import Note, NOTE_TYPE, SUSTAIN_STAGE
from pyday_night_funkin.utils import ListWindow

if t.TYPE_CHECKING:
	from pyday_night_funkin.level import Level


class NoteHandler:
	"""
	Class responsible for spawning, moving and deleting notes as well
	as processing key input.
	"""

	NOTE_TO_CONTROL_MAP = {
		NOTE_TYPE.LEFT: CONTROL.LEFT,
		NOTE_TYPE.DOWN: CONTROL.DOWN,
		NOTE_TYPE.UP: CONTROL.UP,
		NOTE_TYPE.RIGHT: CONTROL.RIGHT,
	}

	def __init__(self, level: "Level", note_layer: str, note_camera: str) -> None:
		self.level = level
		self.note_layer = note_layer
		self.note_camera = note_camera

		self.game_scene = level.game_scene

		self.scroll_speed = level.game_scene.game.config.scroll_speed

		self.notes: t.List[Note] = []
		# Notes that are on screen and have a sprite registered.
		# (May not actually be visible since they may have been played)
		self.notes_visible = ListWindow(self.notes, 0, 0)
		# Notes that are playable based solely on their song position.
		# (These may actually have been played or - for absurd scroll
		# speeds - be invisible.)
		self.notes_playable = ListWindow(self.notes, 0, 0)

		note_assets = ASSETS.XML.NOTES.load()
		self.note_sprites = {
			SUSTAIN_STAGE.NONE: {
				NOTE_TYPE.LEFT: note_assets["purple"][0],
				NOTE_TYPE.DOWN: note_assets["blue"][0],
				NOTE_TYPE.UP: note_assets["green"][0],
				NOTE_TYPE.RIGHT: note_assets["red"][0],
			},
			SUSTAIN_STAGE.TRAIL: {
				NOTE_TYPE.LEFT: note_assets["purple hold piece"][0],
				NOTE_TYPE.DOWN: note_assets["blue hold piece"][0],
				NOTE_TYPE.UP: note_assets["green hold piece"][0],
				NOTE_TYPE.RIGHT: note_assets["red hold piece"][0],
			},
			SUSTAIN_STAGE.END: {
				# this is the worst naming of anything i have ever seen
				NOTE_TYPE.LEFT: note_assets["pruple end hold"][0],
				NOTE_TYPE.DOWN: note_assets["blue hold end"][0],
				NOTE_TYPE.UP: note_assets["green hold end"][0],
				NOTE_TYPE.RIGHT: note_assets["red hold end"][0],
			},
		}

	def feed_song_data(self, song_data) -> None:
		"""
		Supply the NoteHandler with song data which it needs to
		generate the notes. This should happen before any calls
		to `update`!
		"""
		self.scroll_speed *= song_data["song"]["speed"]
		for section in song_data["song"]["notes"]:
			for time_, type_, sustain in section["sectionNotes"]:
				singer = int(section["mustHitSection"]) # 0: opponent, 1: bf
				if type_ >= len(NOTE_TYPE): # Note is sung by other character
					type_ %= len(NOTE_TYPE)
					singer ^= 1
				type_ = NOTE_TYPE(type_)
				note = Note(singer, time_, type_, sustain, SUSTAIN_STAGE.NONE)
				self.notes.append(note)
				trail_notes = math.ceil(sustain / self.level.conductor.step_duration)
				for i in range(trail_notes): # 0 and effectless for non-sustain notes.
					sust_time = time_ + (self.level.conductor.step_duration * (i + 1))
					stage = SUSTAIN_STAGE.END if i == trail_notes - 1 else SUSTAIN_STAGE.TRAIL
					sust_note = Note(singer, sust_time, type_, sustain, stage)
					self.notes.append(sust_note)
		self.notes.sort()

	def update(
		self,
		pressed: t.Dict[NOTE_TYPE, bool],
	) -> t.Tuple[t.List[Note], t.List[Note], t.Dict[NOTE_TYPE, t.Optional[Note]]]:
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
		# NOTE: Could create methods on the ListWindow to eliminate
		# "grow, update-shrink" code duplication

		song_pos = self.level.conductor.song_position

		# Pixels a note traverses in a millisecond
		speed = 0.45 * self.scroll_speed
		note_vis_window_time = (CNST.GAME_HEIGHT - CNST.STATIC_ARROW_Y) / speed
		# NOTE: Makes assumption they're all the same (spoilers: they are)
		arrow_width = self.note_sprites[SUSTAIN_STAGE.NONE][NOTE_TYPE.UP].texture.width * 0.7
		
		# Checks for notes that entered the visibility window, creates their sprites.
		while (
			self.notes_visible.end < len(self.notes) and
			self.notes[self.notes_visible.end].time - song_pos <= note_vis_window_time
		):
			cur_note = self.notes[self.notes_visible.end]
			x = 50 + (CNST.GAME_WIDTH // 2) * cur_note.singer + \
				cur_note.type.get_order() * arrow_width
			texture = self.note_sprites[cur_note.sustain_stage][cur_note.type].texture
			sprite = self.game_scene.create_sprite(
				self.note_layer, self.note_camera, x = x, y = -2000, image = texture
			)
			sprite.scale = 0.7
			if cur_note.sustain_stage != SUSTAIN_STAGE.NONE:
				sprite.x += (arrow_width - texture.width) // 2
				if cur_note.sustain_stage is SUSTAIN_STAGE.TRAIL:
					sprite.scale_y = self.level.conductor.step_duration * \
						0.015 * self.scroll_speed
			cur_note.sprite = sprite
			self.notes_visible.end += 1

		# Updates and shrinks visible notes window, makes played notes invisible,
		# deletes off-screen ones.
		deletion_bound = 0
		for i, note in enumerate(self.notes_visible):
			note_y = CNST.STATIC_ARROW_Y - (song_pos - note.time) * speed
			if note_y < -note.sprite.height:
				deletion_bound = max(deletion_bound, i + 1)
			elif note.rating is not None:
				note.sprite.visible = False
			else:
				note.sprite.y = note_y
		for idx in range(self.notes_visible.start, self.notes_visible.start + deletion_bound):
			self.game_scene.remove_sprite(self.notes[idx].sprite)
			self.notes[idx].sprite = None
			self.notes_visible.start += 1

		# Finds new playable notes
		while (
			self.notes_playable.end < len(self.notes) and
			self.notes[self.notes_playable.end].is_playable(
				song_pos,
				self.game_scene.game.config.safe_window,
			)
		):
			self.notes_playable.end += 1

		# Updates playable notes and shrinks playable notes window by removing missed notes.
		missed_notes = []
		opponent_hit_notes = []
		deletion_bound = 0
		for i, note in enumerate(self.notes_playable):
			prev_hitstate = note.rating
			note.check_playability(song_pos, self.game_scene.game.config.safe_window)
			if prev_hitstate != note.rating and note.singer == 0:
				opponent_hit_notes.append(note)
			if not note.is_playable(song_pos, self.game_scene.game.config.safe_window):
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
				(pressed[note.type] or note.sustain_stage is not SUSTAIN_STAGE.NONE)
			):
				# Congrats, note hit
				res_hit_map[note.type] = note

		return opponent_hit_notes, missed_notes, res_hit_map
