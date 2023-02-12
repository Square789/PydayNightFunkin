
from math import floor
import typing as t


class BPMChangeEvent:
	__slots__ = ("step", "song_time", "bpm")

	def __init__(self, step: int, song_time: float, bpm: float) -> None:
		self.step = step
		self.song_time = song_time
		self.bpm = bpm


# The conductor logic does not perform the smoothing outlined in `dev_notes/quality_post.png`.
# Base FNF also doesn't, from what i can tell; looks like both OpenFL/HF and pyglet are handling
# time well.

# The tiniest conductor
class Conductor:
	# https://ninjamuffin99.newgrounds.com/news/post/1124589
	# -> https://old.reddit.com/r/gamedev/comments/2fxvk4/
	# heres_a_quick_and_dirty_guide_i_just_wrote_how_to/
	# Very awesome tutorial, many thanks

	def __init__(self) -> None:
		self._bpm: float = 1.0

		self.beat_duration: float
		"""
		The duration of a beat, in milliseconds.
		"""

		self.step_duration: float
		"""
		The duration of a step (quarter-beat), in milliseconds.
		"""

		# set it to 1, which no song ever has, so it's hopefully an obvious
		# enough default value. This prevents errors when scene code doesn't
		# set `self.conductor.bpm`, which i don't want to force as it'd be a
		# horrifyingly gross way of required initialization.
		self.bpm = 1.0

		self.song_position = 0.0
		self._bpm_changes: t.List[BPMChangeEvent] = []

	@property
	def bpm(self) -> t.Optional[float]:
		return self._bpm

	@bpm.setter
	def bpm(self, new_bpm: float) -> None:
		if new_bpm <= 0:
			raise ValueError("Bpm can't be lower than or equal to zero!")
		if new_bpm > 420:
			# Scared of flooding with calls to `beat_hit`
			raise ValueError("Bpm too extreme!")
		self._bpm = new_bpm
		self.beat_duration = 60000.0 / new_bpm
		# step is just a quarter beat duration; idk about music this probably has a reason.
		# - ha, now i know 5% more about music, FNF hardcodes everything to a 4/4 time sig.
		# Too bad!
		self.step_duration = self.beat_duration / 4.0

	def get_last_bpm_change(self) -> BPMChangeEvent:
		"""
		Retrieves the last BPM change event.
		If no BPM changes were loaded, will be of the standard BPM at
		step `0` and time `0.0`.
		"""
		r = BPMChangeEvent(0, 0.0, self._bpm)
		for change in self._bpm_changes:
			if self.song_position >= change.song_time:
				r = change
			else:
				break
		return r

	def get_current_step(self) -> int:
		"""
		Returns the step the conductor is in, according to the bpm
		changes registered with it and song time.
		"""
		lc = self.get_last_bpm_change()
		new_step = lc.step + floor((self.song_position - lc.song_time) / self.step_duration)
		return new_step

	def load_bpm_changes(self, song_data: t.Dict) -> None:
		"""
		Loads all bpm change events into the conductor from a song data
		dict.
		"""
		bpm_changes = []
		cur_bpm = song_data["bpm"]
		total_steps = 0
		total_pos = 0.0
		for section in song_data["notes"]:
			if "changeBPM" in section and section["changeBPM"] and section["bpm"] != cur_bpm:
				cur_bpm = section["bpm"]
				bpm_changes.append(BPMChangeEvent(total_steps, total_pos, cur_bpm))

			if isinstance(section["lengthInSteps"], float):
				raise TypeError("Step length must be an int!")
			step_delta = section["lengthInSteps"]
			total_steps += step_delta
			total_pos += (15000.0 / cur_bpm) * step_delta

		self._bpm_changes = bpm_changes
