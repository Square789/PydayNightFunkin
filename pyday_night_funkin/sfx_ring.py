
import typing as t

from pyglet.media import Player

if t.TYPE_CHECKING:
	from pyglet.media import Source


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
		self.players = [Player() for _ in range(player_amount)]
		self._busy = set()
		self.free_player = 0

	def play(self, source: "Source", fail_loudly: bool = False) -> None:
		if self.free_player is None:
			if fail_loudly:
				raise SFXRingFullException("Couldn't queue sound, all players busy.")
			return

		id_ = self.free_player
		player = self.players[self.free_player]

		@player.event("on_eos")
		def _unregister_busy():
			self._busy.remove(id_)

		player.queue(source)
		player.play()
		self._busy.add(id_)
		self.free_player = self._get_free_player()

	def _get_free_player(self) -> t.Optional[int]:
		for i, _ in enumerate(self.players):
			if i not in self._busy:
				return i
		return None
