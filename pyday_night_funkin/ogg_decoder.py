
from loguru import logger
import typing as t

from pyglet.media import Source, StaticSource, StreamingSource
from pyglet.media.codecs import AudioData, AudioFormat, MediaDecoder

from pyday_night_funkin.stb_vorbis import STBVorbis

if t.TYPE_CHECKING:
	from pathlib import Path


class OggVorbisStreamingSource(StreamingSource):
	"""
	Streaming source over an ogg vorbis file.
	"""
	def __init__(self, filename: t.Union[str, "Path"]) -> None:
		"""
		Creates a new OggVorbisStreamingSource. The filename given
		should point to a valid ogg vorbis ogg file, otherwise a
		RuntimeError will be raised.
		"""
		self._stbv = STBVorbis(str(filename))
		self.fallback_sample_pos = 0

		self.audio_format = AudioFormat(self._stbv.channel_amount, 16, self._stbv.sample_rate)
		self._duration = self._stbv.get_duration()

	def get_audio_data(
		self, num_bytes: int, compensation_time: float = 0.0
	) -> t.Optional[AudioData]:
		if compensation_time != 0:
			logger.warning(f"Ignored compensation time was not 0, but {compensation_time}!")

		sample_pos = self._stbv.get_sample_offset()
		if sample_pos == -1:
			logger.warning("Sample position is -1, using possibly inaccurate fallback value!")
			sample_pos = self.fallback_sample_pos

		samples_per_chan, data = self._stbv.get_samples_short_interleaved(num_bytes // 2)
		sample_rate = self._stbv.sample_rate
		read_samples = samples_per_chan * self._stbv.channel_amount
		read_bytes = read_samples * 2
		if read_samples == 0:
			return None

		if read_bytes != len(data):
			# NOTE: this probably involves copying the entire audio buffer just to trim it
			data = data[0 : read_bytes]

		return AudioData(data, len(data), sample_pos / sample_rate, read_samples / sample_rate, [])

	def seek(self, timestamp: float) -> None:
		target_sample = int(timestamp * self._stbv.sample_rate)
		self._stbv.seek(target_sample)
		self.fallback_sample_pos = target_sample


class OggVorbisDecoder(MediaDecoder):
	def get_file_extensions(self) -> t.Tuple[str, ...]:
		return (".ogg", )

	def decode(self, file: t.BinaryIO, filename: str, streaming: bool) -> Source:
		if file is not None and not file.closed:
			file.close()

		src = OggVorbisStreamingSource(filename)
		if streaming:
			return src
		else:
			return StaticSource(src)

_ogg_decoder = OggVorbisDecoder()

def get_decoders():
	return [_ogg_decoder]
