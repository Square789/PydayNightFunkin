
class STBVorbisException(RuntimeError):
	pass

def _get_error_string(err: int) -> str:
	...


class STBVorbis:
	def __init__(self, file_name: str) -> None:
		...

	@property
	def channel_amount(self) -> float:
		"""
		Shortcut to the info's channel count.
		"""

	@property
	def sample_rate(self) -> int:
		"""
		Shortcut to the info's sample rate.
		"""

	def get_info(self) -> dict:
		"""
		Returns a dict mapping the stb_vorbis_info field names to the
		concrete values of this stb_vorbis struct.
		"""

	def get_sample_offset(self) -> int:
		"""
		Returns the sample offset or -1 if it is somehow invalid.
		"""

	def get_samples_short_interleaved(self, num_samples: int) -> tuple[int, bytes]:
		"""
		Returns a tuple of the samples per channel as returned by the
		stb_vorbis library and at most `num_samples` shorts (16 bit) in
		a bytes object for all channels on the stb_vorbis struct, less
		if the data source is exhausted.
		"""

	def get_sample_amount(self) -> int:
		"""
		Returns the total stream length in samples.
		"""

	def get_duration(self) -> float:
		"""
		Returns the total stream length in seconds.
		"""

	def seek(self, target_sample: int) -> None:
		"""
		Seeks to the given sample.
		"""
