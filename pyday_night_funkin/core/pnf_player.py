
import typing as t

from pyglet.media import Player

from pyday_night_funkin.core.constants import SFX_RING_SIZE

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

	def delete(self) -> None:
		self._set_playing(False)
		super().delete()


class SFXRingFullException(RuntimeError):
	pass


class SFXRing():
	"""
	Ring of players to play a (limited) number of sounds
	simultaneously.
	"""

	def __init__(self, player_amount: int = SFX_RING_SIZE) -> None:
		if player_amount <= 0:
			raise ValueError("You must construct additional players! (Seriously, at least 1.)")
		self.players = [PNFPlayer() for _ in range(player_amount)]
		self._busy = set()

	def play(self, source: "Source") -> bool:
		"""
		Plays the given sound source in one of the available players.
		If no player is available, does nothing.
		Returns whether the sound was actually played.
		"""
		free_player_idx = self._get_free_player()
		if free_player_idx is None:
			return False

		player = self.players[free_player_idx]

		def _unregister_busy(player_self=player, player_idx=free_player_idx):
			# I have seen a very elusive bug where this being `remove` causes a
			# KeyError in very specific timing with scene destruction.
			# Use discard to get around that error.
			self._busy.discard(player_idx)
			player_self.pop_handlers()

		player.push_handlers(on_eos=_unregister_busy)
		player.set(source)
		self._busy.add(free_player_idx)

		return True

	def _get_free_player(self) -> t.Optional[int]:
		for i, _ in enumerate(self.players):
			if i not in self._busy:
				return i
		return None

	def delete(self) -> None:
		"""
		Deletes all players contained in the SFXRing and
		renders it unusable.
		"""
		for player in self.players:
			player.delete()
		# Kinda unnecessary but i like me some good cleanup
		del self.players
