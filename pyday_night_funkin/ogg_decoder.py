
import typing as t

from pyglet.media import StaticSource, StreamingSource
from pyglet.media.codecs.base import AudioData

from pyday_night_funkin.stb_vorbis import STBVorbis

class OggVorbisStreamingSource(StreamingSource):
	def __init__(self, filename: str,) -> None:
		self._stbv = STBVorbis(filename)

	def get_audio_data(self, num_bytes, compensation_time) -> AudioData:
		pass

	def seek(self, timestamp: float) -> None:
		pass


class OggVorbisStaticSource(StaticSource):
	def __init__(self, source) -> None:
		pass
