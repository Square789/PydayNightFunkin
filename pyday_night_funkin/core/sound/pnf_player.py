"""
As usual, a significantly modified copypaste of pyglet's Player class.
It is capable of playing audio while linked to a SoundController and
sports some handy additions that make interacting with the queued
sources not as weird.
"""

from collections import deque
from math import e
import typing as t

from pyglet import clock
from pyglet.event import EventDispatcher
from pyglet.media import get_audio_driver
from pyglet.media.codecs.base import Source
from pyglet.media.player import PlaybackTimer

from pyday_night_funkin.core.utils import clamp

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.sound.controller import SoundController


# NOTE: The original Player is ambiguous in whether it allows `pyglet.media.SourceGroup`s.
# I have removed them from the PNFPlayer for the sake of simplicity.
# NOTE: The PNFPlayer can not play video (will probably subclass that back in once the time comes).
# NOTE: The PNFPlayer does not treat stuff queued on it as playlists that are really a 2d-ish
# iterator array of sources, but just a single flat deque of them. This makes some smartass-stuff
# like using `itertools.cycle` as an infinite source impossible, but no one does that (just use loop
# instead), so we're fine like this.

def _make_player_property(name: str, doc: str) -> property:
	# Take away my coding license
	loc = {}
	fname_get = f"_gen_get_{name}"
	fname_set = f"_gen_set_{name}"
	exec(
		(
			f"def {fname_get}(self):\n"
			f"    return self._{name}\n"
		),
		None,
		loc,
	)
	exec(
		(
			f"def {fname_set}(self, new):\n"
			f"    self._{name} = new\n"
			f"    if self._audio_player is not None:\n"
			f"        self._audio_player.set_{name}(new)\n"
		),
		None,
		loc,
	)
	return property(loc[fname_get], loc[fname_set], None, doc)


class PNFPlayer(EventDispatcher):
	# Spacialisation attributes, preserved between audio players
	_volume = 1.0
	_min_distance = 1.0
	_max_distance = 100000000.

	_position = (0, 0, 0)
	_pitch = 1.0

	_cone_orientation = (0, 0, 1)
	_cone_inner_angle = 360.
	_cone_outer_angle = 360.
	_cone_outer_gain = 1.

	def __init__(self, controller: "SoundController") -> None:
		self._source: t.Optional[Source] = None
		self._queued_sources: t.Deque[Source] = deque()
		self._audio_player = None

		self._will_play = False
		"""Desired play state (not an indication of actual state)."""

		self._timer = PlaybackTimer()
		self.loop = False
		"""
		Whether to loop the current source indefinitely or until
		`next_source` is called. Defaults to `False`.
		"""

		self.last_seek_time = 0.0

		self.controller = controller

	def __del__(self):
		# Do not free resources here. __del__ can not be trusted, leaking is preferrable
		if self._audio_player is not None:
			raise ResourceWarning("You're leaking a player!")

	def queue(self, source: t.Union[Source, t.Iterable[Source]]) -> None:
		"""
		Queues a source on this player.
		If the player has no source, the player might start to play
		immediately depending on its `_will_play` attribute.
		"""
		if isinstance(source, Source):
			source = (source,)
		else:
			try:
				source = tuple(source)
			except TypeError:
				raise TypeError(
					f"Source must be either a Source or an iterable. Received type {type(source)}"
				)
			if not source:
				raise TypeError("Must specify at least one source to queue")

		self._queued_sources.extend(source)

		if self.source is None:
			nsource = self._queued_sources.popleft()
			self._source = nsource.get_queue_source()

		self._set_play_desire(self._will_play)

	def _set_play_desire(self, _will_play: bool) -> None:
		self._will_play = _will_play
		source = self.source

		if _will_play and source:
			if source.audio_format:
				if self._audio_player is None:
					self._create_audio_player()
				if self._audio_player is not None:
					# We succesfully created an audio player
					self._audio_player.prefill_audio()

			if source.video_format:
				raise ValueError("PNFPlayers can only play sound.")

			if self._audio_player is not None:
				self._audio_player.play()

			self._timer.start()
			if self._audio_player is None:
				clock.schedule_once(lambda _: self.dispatch_event("on_eos"), source.duration)

		else:
			if self._audio_player is not None:
				self._audio_player.stop()

			self._timer.pause()

	@property
	def playing(self) -> bool:
		"""
		Returns whether the player is playing something.
		This is assumed to be the case when the player has a source
		and its play desire is `True`.
		"""
		return self._will_play and (self.source is not None)

	@property
	def will_play(self) -> bool:
		"""
		Read-only. Returns whether the player's state is playing.

		The `_will_play` property is irrespective of whether or not
		there is actually a source to play. If `_will_play` is `True`
		and a source is queued, it will begin to play immediately.
		If `_will_play` is `False`, it is implied that the player is
		paused.
		There is no other possible state.
		"""
		return self._will_play

	def play(self) -> None:
		"""
		Begins playing the current source.
		This has no effect if the player is already playing.
		"""
		self._set_play_desire(True)

	def pause(self) -> None:
		"""
		Pauses playback of the current source.
		This has no effect if the player is already paused.
		"""
		self._set_play_desire(False)

	def delete(self) -> None:
		"""
		Releases the resources acquired by this player.
		The internal audio player will be deleted.
		"""
		if self._source is not None:
			self._source.is_player_source = False
			self._source = None
		if self._audio_player is not None:
			self._audio_player.delete()
			self._audio_player = None

	def next_source(self):
		"""
		Move to the next source in the current playlist immediately.

		If the playlist is empty, discard it and check if another
		playlist is queued. There may be a gap in playback while the
		audio buffer is refilled.
		"""
		old_play_desire = self._will_play
		self.pause()
		self._timer.reset()

		if self._source:
			# Reset possibly existing source to the beginning and disown
			self.seek(0.0)
			self.source.is_player_source = False

		if not self._queued_sources:
			self._source = None
			self.delete()
			self.dispatch_event("on_player_eos")
			return

		old_audio_format = self._source.audio_format
		self._source = self._queued_sources.popleft().get_queue_source()

		if self._audio_player is not None:
			if old_audio_format == self._source.audio_format:
				self._audio_player.clear()
				self._audio_player.source = self._source
			else:
				self._audio_player.delete()
				self._audio_player = None

		self._set_play_desire(old_play_desire)
		self.dispatch_event("on_player_next_source")

	def seek(self, timestamp: float) -> None:
		"""
		Seek for playback to the indicated timestamp on the current
		source.
		`timestamp` is expressed in seconds, clamped to the end of the
		source if outside of its duration.
		"""
		_play_desire = self._will_play
		if _play_desire:
			self.pause()

		if not self.source:
			return

		timestamp = max(timestamp, 0.0)
		if self._source.duration is not None:
			# TODO: If the duration is reported as None and the source clamps anyways,
			# this will have pretty bad effects.
			# Maybe have seek methods return the timestamp they actually seeked to
			timestamp = min(timestamp, self._source.duration)

		self._timer.set_time(timestamp)
		self._source.seek(timestamp)
		self.last_seek_time = timestamp
		if self._audio_player is not None:
			# XXX: According to docstring in AbstractAudioPlayer this cannot
			# be called when the player is not stopped
			self._audio_player.clear()
		self._set_play_desire(_play_desire)

	def _create_audio_player(self):
		assert not self._audio_player
		assert self.source

		audio_driver = get_audio_driver()
		if audio_driver is None:
			# Failed to find a valid audio driver
			return

		self._audio_player = audio_driver.create_audio_player(self.source, self)
		self._copy_attributes_to_audio_player()

	def _copy_attributes_to_audio_player(self) -> None:
		ap = self._audio_player
		ap.set_volume(self.true_volume)
		ap.set_min_distance(self._min_distance)
		ap.set_max_distance(self._max_distance)
		ap.set_position(self._position)
		ap.set_pitch(self._pitch)
		ap.set_cone_orientation(self._cone_orientation)
		ap.set_cone_inner_angle(self._cone_inner_angle)
		ap.set_cone_outer_angle(self._cone_outer_angle)
		ap.set_cone_outer_gain(self._cone_outer_gain)

	@property
	def source(self) -> t.Optional[Source]:
		"""Returns the current `Source` or `None`."""
		return self._source

	@property
	def time(self):
		"""
		Read-only. Current playback time of the current source.

		The playback time is a float expressed in seconds, with 0.0
		being the beginning of the media.
		"""
		# [snipped from docstring] The playback time returned represents the
		# player master clock time which is used to synchronize both the audio
		# and the video.
		return self._timer.get_time()

	@property
	def volume(self) -> float:
		"""
		The volume level of sound playback.
		The nominal level is 1.0, and 0.0 is silence.
		The volume level is affected by the distance from the listener (if
		positioned).
		Do note this volume may not be the true volume set on the
		audio player. See `true_volume`.
		"""
		return self._volume

	@volume.setter
	def volume(self, new: float) -> None:
		self._volume = new
		normalized = self.true_volume
		if self._audio_player is not None:
			self._audio_player.set_volume(normalized)

	@property
	def true_volume(self) -> float:
		"""
		The actual volume the PNFPlayer will set on its audio
		player. This is its own volume multiplied by the controller's
		volume, clamped between 0. and 1., and raised to the power of
		`e`.
		"""
		# Thanks to this thread:
		# https://www.reddit.com/r/gamedev/comments/7hht15/developers_fix_your_volume_sliders/
		# the OP seems to have delusions of grandeur, but was pretty helpful nonetheless
		return pow(clamp(self._volume * self.controller.volume, 0.0, 1.0), e)

	min_distance = _make_player_property(
		"min_distance",
		"""
		The distance beyond which the sound volume drops by half, and within
		which no attenuation is applied.

		The minimum distance controls how quickly a sound is attenuated as it
		moves away from the listener. The gain is clamped at the nominal value
		within the min distance. By default the value is 1.0.

		The unit defaults to meters, but can be modified with the listener
		properties.
		""",
	)

	max_distance = _make_player_property(
		"max_distance",
		"""
		The distance at which no further attenuation is applied.

		When the distance from the listener to the player is greater than this
		value, attenuation is calculated as if the distance were value. By
		default the maximum distance is infinity.

		The unit defaults to meters, but can be modified with the listener
		properties.
		""",
	)

	position = _make_player_property(
		"position",
		"""
		The position of the sound in 3D space.

		The position is given as a tuple of floats (x, y, z). The unit
		defaults to meters, but can be modified with the listener properties.
		""",
	)

	pitch = _make_player_property(
		"pitch",
		"""
		The pitch shift to apply to the sound.

		The nominal pitch is 1.0. A pitch of 2.0 will sound one octave higher,
		and play twice as fast. A pitch of 0.5 will sound one octave lower, and
		play twice as slow. A pitch of 0.0 is not permitted.
		""",
	)

	cone_orientation = _make_player_property(
		"cone_orientation",
		"""
		The direction of the sound in 3D space.

		The direction is specified as a tuple of floats (x, y, z), and has no
		unit. The default direction is (0, 0, -1). Directional effects are only
		noticeable if the other cone properties are changed from their default
		values.
		""",
	)

	cone_inner_angle = _make_player_property(
		"cone_inner_angle",
		"""
		The interior angle of the inner cone.

		The angle is given in degrees, and defaults to 360. When the listener
		is positioned within the volume defined by the inner cone, the sound is
		played at normal gain (see :attr:`volume`).
		""",
	)

	cone_outer_angle = _make_player_property(
		"cone_outer_angle",
		"""
		The interior angle of the outer cone.

		The angle is given in degrees, and defaults to 360. When the listener
		is positioned within the volume defined by the outer cone, but outside
		the volume defined by the inner cone, the gain applied is a smooth
		interpolation between :attr:`volume` and :attr:`cone_outer_gain`.
		""",
	)

	cone_outer_gain = _make_player_property(
		"cone_outer_gain",
		"""
		The gain applied outside the cone.

		When the listener is positioned outside the volume defined by the outer
		cone, this gain is applied instead of :attr:`volume`.
		""",
	)

	# Events

	def on_player_eos(self):
		"""The player ran out of sources. The playlist is empty.

		:event:
		"""

	def on_eos(self):
		"""The current source ran out of data.

		The default behaviour is to advance to the next source in the
		playlist if the :attr:`.loop` attribute is set to ``False``.
		If :attr:`.loop` attribute is set to ``True``, the current source
		will start to play again until :meth:`next_source` is called or
		:attr:`.loop` is set to ``False``.

		:event:
		"""
		if not self.loop:
			self.next_source()
			return

		old_play_desire = self._will_play
		# Calling `_audio_player.clear()` is illegal when playing
		self._set_play_desire(False)

		self._timer.reset()
		if self.source:
			self.seek(0.0)
		if self._audio_player is not None:
			self._audio_player.clear()
		self._set_play_desire(old_play_desire)

	def on_player_next_source(self):
		"""
		The player starts to play the next queued source in the playlist.

		This is a useful event for adjusting the window size to the new
		source :class:`VideoFormat` for example.

		:event:
		"""
		pass

	def on_driver_reset(self):
		"""
		The audio driver has been reset, by default this will kill the
		current audio player and create a new one, and requeue the buffers.
		Any buffers that may have been queued in a player will be resubmitted.
		It will continue from the last buffers submitted and not played.

		:event:
		"""
		# [snipped from docstring] not played and may cause sync issues if using video.
		if self._audio_player is not None:
			self._audio_player.on_driver_reset()

			# Voice has been changed, will need to reset all options on the voice.
			self._copy_attributes_to_audio_player()

			if self._will_play:
				self._audio_player.play()

	# PNF additions

	def set(self, source: t.Union[Source, t.Iterable[Source]]) -> None:
		"""
		Stops all running playbacks, clears the playlist and
		immediatedly causes the player to start playing the newly
		supplied source.
		"""
		self.stop()
		self.queue(source)
		self._set_play_desire(True)

	def stop(self) -> None:
		"""
		Stops the player by pausing it, clearing all queued sources,
		then advancing away from the current source.
		"""
		self._set_play_desire(False)
		self._queued_sources.clear()
		self.next_source()

	def destroy(self) -> None:
		"""
		Not to be confused with `delete`, this function unlinks the
		player from its controller and also calls `delete` for good
		measure. The player should probably not be used anymore.
		"""
		self.controller.remove_player(self)
		del self.controller
		self.delete()

PNFPlayer.register_event_type("on_eos")
PNFPlayer.register_event_type("on_player_eos")
PNFPlayer.register_event_type("on_player_next_source")
PNFPlayer.register_event_type("on_driver_reset")
