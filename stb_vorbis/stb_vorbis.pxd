
cdef extern from "stb_vorbis.c":
	ctypedef struct stb_vorbis:
		pass


	ctypedef struct stb_vorbis_info:
		unsigned int sample_rate
		int channels

		unsigned int setup_memory_required
		unsigned int setup_temp_memory_required
		unsigned int temp_memory_required

		int max_frame_size


	ctypedef struct stb_vorbis_alloc:
		pass


	cdef enum STBVorbisError:
		VORBIS__no_error,
		VORBIS_need_more_data = 1,
		VORBIS_invalid_api_mixing,
		VORBIS_outofmem,
		VORBIS_feature_not_supported,
		VORBIS_too_many_channels,
		VORBIS_file_open_failure,
		VORBIS_seek_without_length,
		VORBIS_unexpected_eof = 10,
		VORBIS_seek_invalid,
		VORBIS_invalid_setup = 20,
		VORBIS_invalid_stream,
		VORBIS_missing_capture_pattern = 30,
		VORBIS_invalid_stream_structure_version,
		VORBIS_continued_packet_flag_invalid,
		VORBIS_incorrect_stream_serial_number,
		VORBIS_invalid_first_page,
		VORBIS_bad_packet_type,
		VORBIS_cant_find_last_page,
		VORBIS_seek_failed,
		VORBIS_ogg_skeleton_not_supported


	stb_vorbis *stb_vorbis_open_filename(char *file_name, int *error, stb_vorbis_alloc *alloc_buffer)
	void stb_vorbis_close(stb_vorbis *self)
	stb_vorbis_info stb_vorbis_get_info(stb_vorbis *self)
	int stb_vorbis_get_error(stb_vorbis *self)
	int stb_vorbis_get_sample_offset(stb_vorbis *self)
	int stb_vorbis_get_samples_short_interleaved(stb_vorbis *self, int channels, short *buffer, int num_shorts)
	unsigned int stb_vorbis_stream_length_in_samples(stb_vorbis *self)
	float stb_vorbis_stream_length_in_seconds(stb_vorbis *self)
	int stb_vorbis_seek(stb_vorbis *self, unsigned int sample_number)

