
import typing as t

from pyglet.media import StaticSource, StreamingSource
import pyogg


class OggSource(StreamingSource):
	def __init__(self, filename: str, file: t.BinaryIO) -> None:
		if file is None:
			file = open(filename, 'rb')

		self._file = file

		# TODO yeah this because having people download ffmpeg or shipping everything
		# converted as wav is mega cringe
