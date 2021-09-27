
import typing as t


class BPMChangeEvent():
	__slots__ = ("step_time", "song_time", "bpm")

	def __init__(self, step_time: float, song_time: float, bpm: float) -> None:
		self.step_time = step_time
		self.song_time = song_time
		self.bpm = bpm


# The tiniest conductor
class Conductor():
	# https://ninjamuffin99.newgrounds.com/news/post/1124589
	# -> https://www.reddit.com/r/gamedev/comments/2fxvk4/
	#    heres_a_quick_and_dirty_guide_i_just_wrote_how_to/
	# Very awesome tutorial, many thanks

	def __init__(self) -> None:
		self._bpm = None
		self.beat_duration = None
		self.step_duration = None
		self.song_position = 0.0
		self._bpm_changes: t.List[BPMChangeEvent] = []

	@property
	def bpm(self) -> t.Optional[float]:
		return self._bpm

	@bpm.setter
	def bpm(self, new_bpm: float) -> None:
		if new_bpm <= 0:
			raise ValueError("Bpm can't be lower than or equal to zero!")
		if new_bpm >= 500:
			# Scared of flooding with calls to `beat_hit`
			raise ValueError("Bpm too extreme!")
		self._bpm = new_bpm
		self.beat_duration = 60000.0 / new_bpm
		# step is just a quarter beat duration
		# idk about music this probably has a reason
		self.step_duration = self.beat_duration / 4.0

	@property
	def last_bpm_change(self) -> BPMChangeEvent:
		r = BPMChangeEvent(0.0, 0.0, 0.0)
		# NOTE: pretty intensive loop, could be kept track of way easier by
		# adding a song_position property
		for change in self._bpm_changes:
			if self.song_position >= change.song_time:
				r = change
			else:
				break
		return r

	def load_bpm_changes(self, song_data) -> None:
		bpm_changes = []
		cur_bpm = song_data["song"]["bpm"]
		total_steps = 0
		total_pos = 0.0
		for section in song_data["song"]["notes"]:
			if "changeBPM" in section and section["changeBPM"] and section["bpm"] != cur_bpm:
				cur_bpm = section["bpm"]
				bpm_changes.append(BPMChangeEvent(total_steps, total_pos, cur_bpm))

			step_delta = section["lengthInSteps"]
			total_steps += step_delta
			total_pos += (15000.0 / cur_bpm) * step_delta

		self._bpm_changes = bpm_changes
