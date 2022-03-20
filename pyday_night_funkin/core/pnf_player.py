
import typing as t

from pyglet.media import Player

if t.TYPE_CHECKING:
	from pyglet.media import Source

class PNFPlayer(Player):
	"""
	Pyglet player subclass that introduces some handy extra methods
	(which really should be on the original player but whatever).
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


class SFXRingFullException(RuntimeError):
	pass


class SFXRing():
	"""
	Ring of players to play a (limited) number of sounds
	simultaneously.
	"""

	def __init__(self, player_amount: int) -> None:
		if player_amount <= 0:
			raise ValueError("You must construct additional players! (Seriously, at least 1.)")
		self.players = [PNFPlayer() for _ in range(player_amount)]
		self._busy = set()

	def play(self, source: "Source", fail_loudly: bool = False) -> None:
		free_player = self._get_free_player()
		if free_player is None:
			if fail_loudly:
				raise SFXRingFullException("Couldn't queue sound, all players busy.")
			return

		player = self.players[free_player]

		def _unregister_busy():
			self._busy.remove(free_player)
			player.pop_handlers()
		player.push_handlers(on_eos = _unregister_busy)

		player.set(source)
		self._busy.add(free_player)

	def _get_free_player(self) -> t.Optional[int]:
		for i, _ in enumerate(self.players):
			if i not in self._busy:
				return i
		return None

	def delete(self) -> None:
		for player in self.players:
			player.stop()
			player.delete()
		self.players = []
		# Unnecessary but i like me some good cleanup
		self._busy = set()