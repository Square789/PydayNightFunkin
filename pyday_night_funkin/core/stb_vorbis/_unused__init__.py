import ctypes
from ctypes import (
	Structure, POINTER, Union, byref, c_char_p, c_float, c_int, c_int16, c_int32, c_short, c_ubyte,
	c_uint, c_uint16, c_uint32, c_uint8, c_void_p, cast, create_string_buffer, sizeof
)
from enum import IntEnum
from pathlib import Path
import typing as t

c_uchar = c_ubyte # don't like the name. it reminds me of java. *shudders*


cwd = Path.cwd()
if cwd.name == "PydayNightFunkin":
	dll_path = cwd / "pyday_night_funkin/core/stb_vorbis/stb_vorbis.dll"
elif cwd.name == "pyday_night_funkin":
	dll_path = cwd / "core/stb_vorbis/stb_vorbis.dll"
else:
	dll_path = Path("./stb_vorbis.dll")
stb_vorbis_lib = ctypes.windll.LoadLibrary(str(dll_path))

# Will be using "is None" as synonym to "#ifndef"
# These have to correspond to the set of macros that the dll was compiled with.
# Though I guess no one will be recompiling stb_vorbis.dll with them changed so whatever
STB_VORBIS_NO_STDIO = None
STB_VORBIS_MAX_CHANNELS = 16
STB_VORBIS_NO_DEFER_FLOOR = None
STB_VORBIS_NO_PUSHDATA_API = None
STB_VORBIS_FAST_HUFFMAN_SHORT = 1
STB_VORBIS_FAST_HUFFMAN_LENGTH = 10
FAST_HUFFMAN_TABLE_SIZE = 1 << STB_VORBIS_FAST_HUFFMAN_LENGTH
FAST_HUFFMAN_TABLE_MASK = FAST_HUFFMAN_TABLE_SIZE - 1

class STB_VORBIS_ERR(IntEnum):
	_no_error = 0
	need_more_data = 1
	invalid_api_mixing = 2
	outofmem = 3
	feature_not_supported = 4
	too_many_channels = 5
	file_open_failure = 6
	seek_without_length = 7
	unexpected_eof = 10
	seek_invalid = 11
	invalid_setup = 20
	invalid_stream = 21
	missing_capture_pattern = 30
	invalid_stream_structure_version = 31
	continued_packet_flag_invalid = 32
	incorrect_stream_serial_number = 33
	invalid_first_page = 34
	bad_packet_type = 35
	cant_find_last_page = 36
	seek_failed = 37
	ogg_skeleton_not_supported = 38

STB_VORBIS_ERR_VALUES = frozenset(v.value for v in STB_VORBIS_ERR.__members__.values())


class stb_vorbis(Structure):
	pass


class stb_vorbis_alloc(Structure):
	_fields_ = [
		("alloc_buffer", c_char_p),
		("alloc_buffer_length_in_bytes", c_int),
	]


class stb_vorbis_info(Structure):
	_fields_ = [
		("sample_rate", c_uint),
		("channels", c_int),
		("setup_memory_required", c_uint),
		("setup_temp_memory_required", c_uint),
		("temp_memory_required", c_uint),
		("max_frame_size", c_int),
	]


class stb_vorbis_comment(Structure):
	_fields_ = [
		("vendor", c_char_p),
		("comment_list_length", c_int),
		("comment_list", POINTER(c_char_p)),
	]


codetype = c_float

class Codebook(Structure):
	_fields = [
		("dimensions", c_int),
		("entries", c_int),
		("codeword_lengths", POINTER(c_uint8)),
		("minimum_value", c_float),
		("delta_value", c_float),
		("value_bits", c_uint8),
		("lookup_type", c_uint8),
		("sequence_p", c_uint8),
		("sparse", c_uint8),
		("lookup_values", c_uint32),
		("multiplicands", POINTER(codetype)),
		("codewords", POINTER(c_uint32)),
		(
			"fast_huffman",
			(c_int16 if STB_VORBIS_FAST_HUFFMAN_SHORT is not None else c_int32) * \
				FAST_HUFFMAN_TABLE_SIZE
		),
		("sorted_codewords", POINTER(c_uint32)),
		("sorted_values", POINTER(c_int)),
		("sorted_entries", c_int),
	]


class Floor0(Structure):
	_fields = [
		("order", c_uint8), 
		("rate", c_uint16), 
		("bark_map_size", c_uint16), 
		("amplitude_bits", c_uint8), 
		("amplitude_offset", c_uint8), 
		("number_of_books", c_uint8), 
		("book_list", c_uint8 * 16), 
	]


class Floor1(Structure):
	_fields = [
		("partitions", c_uint8),
		("partition_class_list", c_uint8 * 32),
		("class_dimensions", c_uint8 * 16),
		("class_subclasses", c_uint8 * 16),
		("class_masterbooks", c_uint8 * 16),
		("subclass_books", (c_int16 * 8) * 16),
		("Xlist", c_uint16 * (31 * 8 + 2)),
		("sorted_order", c_uint8 * (31 * 8 + 2)),
		("neighbors", (c_uint8 * 2) * (31 * 8 + 2)),
		("floor1_multiplier", c_uint8),
		("rangebits", c_uint8),
		("values", c_int),
	]


class Floor(Union):
	_fields = [
		("floor0", Floor0),
		("floor1", Floor1),
	]


class Residue(Structure):
	_fields = [
		("begin", c_uint32),
		("end", c_uint32),
		("part_size", c_uint32),
		("classifications", c_uint8),
		("classbook", c_uint8),
		("classdata", POINTER(POINTER(c_uint8))),
		("residue_books", POINTER(c_int16 * 8)),
	]


class MappingChannel(Structure):
	_fields = [
		("magnitude", c_uint8),
		("angle", c_uint8),
		("mux", c_uint8),
	]


class Mapping(Structure):
	_fields_ = [
		("coupling_steps", c_uint16),
		("chan", POINTER(MappingChannel)),
		("submaps", c_uint8),
		("submap_floor", c_uint8 * 15),
		("submap_residue", c_uint8 * 15),
	]


class Mode(Structure):
	_fields_ = [
		("blockflag", c_uint8),
		("mapping", c_uint8),
		("windowtype", c_uint16),
		("transformtype", c_uint16),
	]


class CRCScan(Structure):
	_fields_ = [
		("goal_crc", c_uint32),
		("bytes_left", c_int),
		("crc_so_far", c_uint32),
		("bytes_done", c_int),
		("sample_loc", c_uint32),
	]


class ProbedPage(Structure):
	_fields_ = [
		("page_start", c_uint32),
		("page_end", c_uint32),
		("last_decoded_sample", c_uint32),
	]

STBVorbisError = c_int

_stb_vorbis_fields = [
	("sample_rate", c_uint),
	("channels", c_int),
	("setup_memory_required", c_uint),
	("temp_memory_required", c_uint),
	("setup_temp_memory_required", c_uint),
	("vendor", c_char_p),
	("comment_list_length", c_int),
	("comment_list", POINTER(c_char_p)),
]
if STB_VORBIS_NO_STDIO is None:
	_stb_vorbis_fields.extend((
		("f", c_void_p),      # FILE unusable!
		("f_start", c_uint32),
		("close_on_free", c_int),
	))
_stb_vorbis_fields.extend((
	("stream", POINTER(c_uint8)),
	("stream_start", POINTER(c_uint8)),
	("stream_end", POINTER(c_uint8)),
	("stream_len", c_uint32),
	("push_mode", c_uint8),
	("first_audio_page_offset", c_uint32),
	("p_first", ProbedPage),
	("p_last", ProbedPage),
	("alloc", stb_vorbis_alloc),
	("setup_offset", c_int),
	("temp_offset", c_int),
	("eof", c_int),
	("error", STBVorbisError),
	("blocksize", c_int * 2),
	("blocksize_0", c_int),
	("blocksize_1", c_int),
	("codebook_count", c_int),
	("codebooks", POINTER(Codebook)),
	("floor_count", c_int),
	("floor_types", c_uint16 * 64),
	("floor_config", POINTER(Floor)),
	("residue_count", c_int),
	("residue_types", c_uint16 * 64),
	("residue_config", POINTER(Residue)),
	("mapping_count", c_int),
	("mapping", POINTER(Mapping)),
	("mode_count", c_int),
	("mode_config", Mode * 64),
	("total_samples", c_uint32),
	("channel_buffers", c_float * STB_VORBIS_MAX_CHANNELS),
	("outputs", POINTER(c_float) * STB_VORBIS_MAX_CHANNELS),
	("previous_window", POINTER(c_float) * STB_VORBIS_MAX_CHANNELS),
	("previous_length", c_int),
	(
		"finalY",
		(c_int16 if STB_VORBIS_NO_DEFER_FLOOR is None else c_float) * \
			STB_VORBIS_MAX_CHANNELS
	),
	("current_loc", c_uint32),
	("current_loc_valid", c_int),
	("A", POINTER(c_float) * 2),
	("B", POINTER(c_float) * 2),
	("C", POINTER(c_float) * 2),
	("window", POINTER(c_float) * 2),
	("bit_reverse", POINTER(c_uint16) * 2),
	("serial", c_uint32),
	("last_page", c_int),
	("segment_count", c_int),
	("segments", c_uint8 * 255),
	("page_flag", c_uint8),
	("bytes_in_seg", c_uint8),
	("first_decode", c_uint8),
	("next_seg", c_int),
	("last_seg", c_int),
	("last_seg_which", c_int),
	("acc", c_uint32),
	("valid_bits", c_int),
	("packet_bytes", c_int),
	("end_seg_with_known_loc", c_int),
	("known_loc_for_packet", c_uint32),
	("discard_samples_deferred", c_int),
	("samples_output", c_uint32),
	("page_crc_tests", c_int),
))
if STB_VORBIS_NO_PUSHDATA_API is None:
	_stb_vorbis_fields.extend((
		("scan", CRCScan),
	))
_stb_vorbis_fields.extend((
	("channel_buffer_start", c_int),
	("channel_buffer_end", c_int),
))

stb_vorbis._fields_ = _stb_vorbis_fields

# === Functions ===

# Ignore line length limit, no one's gonna look at these anyways
stb_vorbis_lib.stb_vorbis_get_info.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_get_info.restype = stb_vorbis_info

stb_vorbis_lib.stb_vorbis_get_comment.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_get_comment.restype = stb_vorbis_comment

stb_vorbis_lib.stb_vorbis_get_error.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_get_error.restype = c_int

stb_vorbis_lib.stb_vorbis_close.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_close.restype = None

stb_vorbis_lib.stb_vorbis_get_sample_offset.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_get_sample_offset.restype = c_int

stb_vorbis_lib.stb_vorbis_get_file_offset.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_get_file_offset.restype = c_uint

stb_vorbis_lib.stb_vorbis_decode_filename.argtypes = [c_char_p, POINTER(c_int), POINTER(c_int), POINTER(POINTER(c_short))]
stb_vorbis_lib.stb_vorbis_decode_filename.restype = c_int

stb_vorbis_lib.stb_vorbis_decode_memory.argtypes = [POINTER(c_uchar), c_int, POINTER(c_int), POINTER(POINTER(c_short))]
stb_vorbis_lib.stb_vorbis_decode_memory.restype = c_int

stb_vorbis_lib.stb_vorbis_open_memory.argtypes = [POINTER(c_uchar), c_int, POINTER(c_int), POINTER(stb_vorbis_alloc)]
stb_vorbis_lib.stb_vorbis_open_memory.restype = POINTER(stb_vorbis)

stb_vorbis_lib.stb_vorbis_open_filename.argtypes = [c_char_p, POINTER(c_int), POINTER(stb_vorbis_alloc)]
stb_vorbis_lib.stb_vorbis_open_filename.restype = POINTER(stb_vorbis)

# arg 0 must be FILE pointer; probably won't be using this function anyways though
stb_vorbis_lib.stb_vorbis_open_file.argtypes = [c_void_p, c_int, POINTER(c_int), POINTER(stb_vorbis_alloc), c_uint]
stb_vorbis_lib.stb_vorbis_open_file.restype = POINTER(stb_vorbis)

# FILE like above
stb_vorbis_lib.stb_vorbis_open_file_section.argtypes = [c_void_p, c_int, POINTER(c_int), POINTER(stb_vorbis_alloc), c_uint]
stb_vorbis_lib.stb_vorbis_open_file_section.restype = POINTER(stb_vorbis)

stb_vorbis_lib.stb_vorbis_seek_frame.argtypes = [POINTER(stb_vorbis), c_uint]
stb_vorbis_lib.stb_vorbis_seek_frame.restype = c_int

stb_vorbis_lib.stb_vorbis_seek.argtypes = [POINTER(stb_vorbis), c_uint]
stb_vorbis_lib.stb_vorbis_seek.restype = c_int

stb_vorbis_lib.stb_vorbis_seek_start.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_seek_start.restype = c_int

stb_vorbis_lib.stb_vorbis_stream_length_in_samples.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_stream_length_in_samples.restype = c_uint

stb_vorbis_lib.stb_vorbis_stream_length_in_seconds.argtypes = [POINTER(stb_vorbis)]
stb_vorbis_lib.stb_vorbis_stream_length_in_seconds.restype = c_float

stb_vorbis_lib.stb_vorbis_get_frame_float.argtypes = [POINTER(stb_vorbis), POINTER(c_int), POINTER(POINTER(POINTER(c_float)))]
stb_vorbis_lib.stb_vorbis_get_frame_float.restype = c_int

stb_vorbis_lib.stb_vorbis_get_frame_short_interleaved.argtypes = [POINTER(stb_vorbis), c_int, POINTER(c_short), c_int]
stb_vorbis_lib.stb_vorbis_get_frame_short_interleaved.restype = c_int

stb_vorbis_lib.stb_vorbis_get_frame_short.argtypes = [POINTER(stb_vorbis), c_int, POINTER(POINTER(c_short)), c_int]
stb_vorbis_lib.stb_vorbis_get_frame_short.restype = c_int

stb_vorbis_lib.stb_vorbis_get_samples_float_interleaved.argtypes = [POINTER(stb_vorbis), c_int, POINTER(c_float), c_int]
stb_vorbis_lib.stb_vorbis_get_samples_float_interleaved.restype = c_int

stb_vorbis_lib.stb_vorbis_get_samples_float.argtypes = [POINTER(stb_vorbis), c_int, POINTER(POINTER(c_float)), c_int]
stb_vorbis_lib.stb_vorbis_get_samples_float.restype = c_int

stb_vorbis_lib.stb_vorbis_get_samples_short_interleaved.argtypes = [POINTER(stb_vorbis), c_int, POINTER(c_short), c_int]
stb_vorbis_lib.stb_vorbis_get_samples_short_interleaved.restype = c_int

stb_vorbis_lib.stb_vorbis_get_samples_short.argtypes = [POINTER(stb_vorbis), c_int, POINTER(POINTER(c_short)), c_int]
stb_vorbis_lib.stb_vorbis_get_samples_short.restype = c_int


class STBVorbisException(Exception):
	pass


class STBVorbis():
	"""
	Python class managing a stb_vorbis struct.
	Only supports the specific subset of functions this project needs
	since I am lazy.
	"""
	def __init__(self, file_path: str, path_encoding: str = "utf-8"):
		# Can't pass in existing file handles since the dll requires a C FILE struct.

		cstr = create_string_buffer(file_path.encode(path_encoding))
		error = c_int()
		alloc = POINTER(stb_vorbis_alloc)()

		self._stb_vorbis = stb_vorbis_lib.stb_vorbis_open_filename(cstr, byref(error), alloc)
		if not self._stb_vorbis:
			raise STBVorbisException(f"Error creating stb_vorbis struct.")

		# These better don't change midway through a file
		self.channel_amount = self._stb_vorbis.contents.channels
		self.sample_rate = self._stb_vorbis.contents.sample_rate

	def __del__(self) -> None:
		if hasattr(self, "_stb_vorbis") and self._stb_vorbis:
			stb_vorbis_lib.stb_vorbis_close(self._stb_vorbis)

	def _get_error_string(self) -> str:
		"""
		Returns a formatted error string of the current error and its
		name as assigned in the STB_VORBIS_ERR enum.
		"""
		err = self._stb_vorbis.contents.error.value
		name = STB_VORBIS_ERR(err).name if err in STB_VORBIS_ERR_VALUES else "?"
		return f"{err} ({name!r})"

	def get_info(self) -> t.Dict[str, t.Any]:
		"""
		Returns a dict mapping the stb_vorbis_info field names to the
		concrete values of this stb_vorbis struct.
		"""
		info = stb_vorbis_lib.stb_vorbis_get_info(self._stb_vorbis)
		if not info:
			raise STBVorbisException(
				f"Getting info failed. stb_vorbis struct error: {self._get_error_string()}"
			)
		return {field: getattr(info, field) for field, _ in stb_vorbis_info._fields_}

	def get_sample_offset(self):
		"""
		Returns the sample offset in the file
		"""
		return stb_vorbis_lib.stb_vorbis_get_sample_offset(self._stb_vorbis)

	def get_samples_short_interleaved(self, samples: int) -> t.Tuple[int, bytes]:
		"""
		Returns a tuple of the samples per channel as returned by the
		stb_vorbis library and at most `samples` shorts (16 bit) in a
		bytes object for all channels on the stb_vorbis struct, less if
		the data source is exhausted.
		"""
		buf = create_string_buffer(sizeof(c_short) * samples)
		cast_buf = cast(buf, POINTER(c_short))

		samples_per_channel = stb_vorbis_lib.stb_vorbis_get_samples_short_interleaved(
			self._stb_vorbis, self.channel_amount, cast_buf, samples
		)

		return (samples_per_channel, buf.raw)

	def get_sample_amount(self) -> int:
		"""
		Returns the total stream length in samples.
		"""
		return stb_vorbis_lib.stb_vorbis_get_stream_length_in_samples(self._stb_vorbis)

	def get_duration(self) -> float:
		"""
		Returns the total stream length in seconds.
		"""
		return stb_vorbis_lib.stb_vorbis_stream_length_in_seconds(self._stb_vorbis)

	def seek(self, target_sample: int) -> None:
		"""
		Seeks to the given sample.
		"""
		# Ignore return value? No idea what it even represents
		stb_vorbis_lib.stb_vorbis_seek(self._stb_vorbis, target_sample)

