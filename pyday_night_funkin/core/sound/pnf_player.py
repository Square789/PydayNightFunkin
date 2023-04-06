
import typing as t

from pyglet.media import Player

if t.TYPE_CHECKING:
	from pyglet.media import Source
	from pyday_night_funkin.core.sound.controller import SoundController



class PNFPlayer(Player):
	"""
	Pyglet player subclass that introduces some handy extra methods
	such as `set` and `stop` and interlinks it with a
	`SoundController`.
	"""

	def __init__(self, controller: "SoundController") -> None:
		super().__init__()

		self.controller = controller

		self._local_volume: float = 1.0
		"""
		The volume that is requested on the player itself.
		"""

	def set(self, source) -> None:
		"""
		Stops all running playbacks, clears the playlist and
		immediatedly causes the player to start playing the newly
		supplied source.
		"""
		self.stop()
		self.queue(source)
		self._set_playing(True)

	def stop(self) -> None:
		"""
		Stops the player by advancing through all sources until it
		is empty.
		"""
		# NOTE: Legit no clue how bad of an idea this is, but works :TM:
		while self._playlists:
			self.next_source()
		self._set_playing(False)

	def destroy(self) -> None:
		"""
		Not to be confused with `delete`, this function unlinks the
		player from its controller and also deletes in internally.
		The player should probably not be used anymore.
		"""
		self.controller.remove_player(self)
		del self.controller
		self.delete()

	@property
	def volume(self) -> float:
		"""
		Local volume of this player. May not be the true volume it's
		playing at.
		"""
		return self._local_volume

	@volume.setter
	def volume(self, new_vol: float) -> None:
		self._local_volume = new_vol
		# HACK: Circumvents the "volume" _PlayerProperty from Player as i can't figure out how
		# to access it. Probably better anyways.
		if self._audio_player is not None:
			self._audio_player.set_volume(new_vol * self.controller.volume)


class SFXRing:
	"""
	Ring of players to play a (limited) number of sounds
	simultaneously.
	"""

	def __init__(self, controller: "SoundController", players: t.List[PNFPlayer]) -> None:
		self.controller = controller
		self.players = players
		self.queue = list(players)

		for player in players:
			def readd_on_eos(lplayer=player) -> None:
				self.queue.append(lplayer)
			player.push_handlers(on_eos=readd_on_eos)

	def play(self, source: "Source") -> bool:
		"""
		Plays the given sound source in one of the available players.
		If no player is available, does nothing.
		Returns whether the sound was actually played.
		"""
		if not self.queue:
			return False

		player = self.queue.pop()
		player.set(source)

		return True

	def destroy(self) -> None:
		"""
		Destroys all players contained in the SFXRing and
		renders it unusable.
		"""
		for player in self.players:
			player.destroy()

		# Kinda unnecessary but i like me some good cleanup
		del self.players
		del self.queue
		del self.controller
