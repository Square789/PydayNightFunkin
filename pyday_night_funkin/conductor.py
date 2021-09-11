
import typing as t

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
