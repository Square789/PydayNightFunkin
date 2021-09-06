
import math
import typing as t

from pyday_night_funkin.asset_system import ASSETS
from pyday_night_funkin.config import KEY
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.note import Note, NOTE_TYPE, SUSTAIN_STAGE
from pyday_night_funkin.utils import ListWindow

if t.TYPE_CHECKING:
	from pyday_night_funkin.levels import Level


class NoteHandler:
	"""
	Class responsible for spawning, moving and deleting notes as well
	as processing key input.
	"""

	def __init__(self, level: "Level") -> None:
		self.level = level
		self.game_scene = level.game_scene
		self.key_handler = level.game_scene.game.key_handler

		self.scroll_speed = level.game_scene.game.config.scroll_speed

		self.notes: t.List[Note] = []
		# Notes in here may not actually be visible since they may
		# have been played.
		self.notes_visible = ListWindow(self.notes, 0, 0)
		# Notes in here may not be visible for absurd scroll speeds.
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
				trail_notes = math.ceil(sustain / self.level.conductor.beat_step_duration)
				for i in range(trail_notes): # 0 and effectless for non-sustain notes.
					sust_time = time_ + (self.level.conductor.beat_step_duration * (i + 1))
					stage = SUSTAIN_STAGE.END if i == trail_notes - 1 else SUSTAIN_STAGE.TRAIL
					sust_note = Note(singer, sust_time, type_, sustain, stage)
					self.notes.append(sust_note)
		self.notes.sort()

	def update(self, dt: float) -> None:
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
			sust_stage = cur_note.sustain_stage # No i am not calling it sus_stage
			texture = self.note_sprites[sust_stage][cur_note.type].texture
			sprite = self.game_scene.create_sprite("ui1", (x, -2000), texture, "ui")
			sprite.world_scale = 0.7
			if sust_stage != SUSTAIN_STAGE.NONE:
				sprite.world_x += (arrow_width - texture.width) // 2
				if sust_stage is SUSTAIN_STAGE.TRAIL:
					sprite.world_scale_y = self.level.conductor.beat_step_duration * \
						0.015 * self.scroll_speed
			cur_note.sprite = sprite
			self.notes_visible.end += 1

		# Updates and shrinks visible notes window, makes played notes invisible,
		# deletes off-screen ones.
		for note in self.notes_visible:
			note_y = CNST.STATIC_ARROW_Y - (song_pos - note.time) * speed
			if note_y < -note.sprite.height:
				self.notes_visible.start += 1
				self.game_scene.remove_sprite(note.sprite)
				note.sprite.delete()
				note.sprite = None
			elif note.hit_state is not None:
				note.sprite.visible = False
			else:
				note.sprite.world_y = note_y

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
		for note in self.notes_playable:
			prev_hitstate = note.hit_state
			note.check_playability(song_pos, self.game_scene.game.config.safe_window)
			if prev_hitstate != note.hit_state and note.singer == 0:
				self.level.opponent.play_animation(f"note_{note.type.name.lower()}")
			if note.missed:
				self.notes_playable.start += 1

		# Key handling oh yeah
		pressed: t.Dict[NOTE_TYPE, t.Optional[Note]] = {}
		just_pressed: t.Dict[NOTE_TYPE, bool] = {}
		for note_type, key in zip(
			(NOTE_TYPE.LEFT, NOTE_TYPE.DOWN, NOTE_TYPE.UP, NOTE_TYPE.RIGHT),
			(KEY.LEFT, KEY.DOWN, KEY.UP, KEY.RIGHT)
		):
			if self.key_handler[key]:
				pressed[note_type] = None
				just_pressed[note_type] = self.key_handler.just_pressed(key)

		for note in self.notes_playable:
			if note.singer != 1 or note.hit_state is not None or note.type not in pressed:
				continue
			if note.type in pressed:
				pressed[note.type] = note

		for note_type in NOTE_TYPE:
			if note_type not in pressed:
				if self.level.static_arrows[1][note_type].current_animation != "static":
					self.level.static_arrows[1][note_type].play_animation("static")
			else:
				if pressed[note_type] is None:
					if (
						self.level.static_arrows[1][note_type].current_animation is not None and
						self.level.static_arrows[1][note_type].current_animation == "static"
					):
						self.level.static_arrows[1][note_type].play_animation("pressed")
						self.level.bf.play_animation(f"note_{note_type.name.lower()}_miss")
				else:
					# looks terrible no matter how i format it
					if (
						(
							pressed[note_type].sustain_stage is SUSTAIN_STAGE.NONE and
							just_pressed[note_type]
						) or (
							pressed[note_type].sustain_stage is not SUSTAIN_STAGE.NONE
						)
					):
						pressed[note_type].on_hit(
							song_pos, self.game_scene.game.config.safe_window
						)
						self.level.bf.play_animation(f"note_{note_type.name.lower()}")
						self.level.static_arrows[1][note_type].play_animation("confirm")
