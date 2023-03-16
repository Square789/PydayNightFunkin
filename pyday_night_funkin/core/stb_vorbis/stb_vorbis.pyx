from pyday_night_funkin.core.stb_vorbis.stb_vorbis cimport *
from libc.stdlib cimport malloc, free


class STBVorbisException(RuntimeError):
	pass


def _get_error_string(int err) -> str:
	cdef str err_str = "Unknown"
	if err == VORBIS__no_error:
		err_str = "No error"
	elif err == VORBIS_need_more_data:
		err_str = "Need more data"
	elif err == VORBIS_invalid_api_mixing:
		err_str = "Invalid API mixing"
	elif err == VORBIS_outofmem:
		err_str = "Out of memory"
	elif err == VORBIS_feature_not_supported:
		err_str = "Feature not supported"
	elif err == VORBIS_too_many_channels:
		err_str = "The amount of channels is too damn high"
	elif err == VORBIS_file_open_failure:
		err_str = "File opening failure"
	elif err == VORBIS_seek_without_length:
		err_str = "Seek without length"
	elif err == VORBIS_unexpected_eof:
		err_str = "Unexpected EOF"
	elif err == VORBIS_seek_invalid:
		err_str = "Seek invalid"
	elif err == VORBIS_invalid_setup:
		err_str = "Invalid setup"
	elif err == VORBIS_invalid_stream:
		err_str = "Invalid stream"
	elif err == VORBIS_missing_capture_pattern:
		err_str = "Missing capture pattern"
	elif err == VORBIS_invalid_stream_structure_version:
		err_str = "Invalid stream structure version"
	elif err == VORBIS_continued_packet_flag_invalid:
		err_str = "Continued packet flag is invalid"
	elif err == VORBIS_incorrect_stream_serial_number:
		err_str = "Incorrect stream serial number"
	elif err == VORBIS_invalid_first_page:
		err_str = "Invalid first page"
	elif err == VORBIS_bad_packet_type:
		err_str = "Bad packet type"
	elif err == VORBIS_cant_find_last_page:
		err_str = "Can't find last page"
	elif err == VORBIS_seek_failed:
		err_str = "Seek failed"
	elif err == VORBIS_ogg_skeleton_not_supported:
		err_str = "Ogg skeleton not supported (2spooky)"

	return f"{err_str} ({err})"


cdef class STBVorbis:
	cdef stb_vorbis *_stb_vorbis

	cdef readonly int channel_amount
	cdef readonly int sample_rate

	def __cinit__(self, file_name: str):
		cdef int open_error = 0

		self._stb_vorbis = stb_vorbis_open_filename(file_name.encode(), &open_error, NULL)
		if self._stb_vorbis == NULL:
			raise STBVorbisException(_get_error_string(open_error))

		cdef stb_vorbis_info info = stb_vorbis_get_info(self._stb_vorbis)
		self.channel_amount = info.channels
		self.sample_rate = info.sample_rate

	def __dealloc__(self):
		if self._stb_vorbis:
			stb_vorbis_close(self._stb_vorbis)

	def get_info(self):
		return stb_vorbis_get_info(self._stb_vorbis)

	def get_sample_offset(self) -> int:
		return stb_vorbis_get_sample_offset(self._stb_vorbis)

	def get_samples_short_interleaved(self, num_samples: int) -> tuple[int, bytes]:
		cdef short *buf = <short *>malloc(sizeof(short) * num_samples)
		if buf == NULL:
			raise MemoryError()

		cdef int samples_per_channel
		samples_per_channel = stb_vorbis_get_samples_short_interleaved(
			self._stb_vorbis, self.channel_amount, buf, num_samples
		)

		cdef int read_samples = samples_per_channel * self.channel_amount
		cdef int read_bytes = read_samples * sizeof(short)

		cdef bytes ret_bytes
		try:
			# Cython needs to believe buf is a string for this truncating
			# syntax to work, should be good like this
			ret_bytes = (<char *>buf)[:read_bytes]
		finally:
			free(buf)

		return (read_samples, ret_bytes)

	def get_sample_amount(self) -> int:
		return stb_vorbis_stream_length_in_samples(self._stb_vorbis)

	def get_duration(self) -> float:
		return stb_vorbis_stream_length_in_seconds(self._stb_vorbis)

	def seek(self, unsigned int target_sample):
		# Ignore return value? No idea what it even represents
		stb_vorbis_seek(self._stb_vorbis, target_sample)
