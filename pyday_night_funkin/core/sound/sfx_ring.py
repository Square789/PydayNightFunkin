
import typing as t

from .pnf_player import PNFPlayer

if t.TYPE_CHECKING:
	from pyglet.media import Source
	from pyday_night_funkin.core.sound.controller import SoundController


class SFXRing:
	"""
	Ring of players to play a (limited) number of sounds
	simultaneously.
	"""

	def __init__(self, controller: "SoundController", players: t.List[PNFPlayer]) -> None:
		self.controller = controller
		self.players: t.List[t.Tuple[PNFPlayer, t.Callable]] = []
		self.queue = list(players)

		for player in players:
			def readd_on_eos(lplayer=player) -> None:
				self.queue.append(lplayer)
			player.push_handlers(on_eos=readd_on_eos)
			self.players.append((player, readd_on_eos))

	def play(self, source: "Source", volume: float = 1.0) -> bool:
		"""
		Plays the given sound source in one of the available players.
		If no player is available, does nothing.
		Returns whether the sound was actually played.
		"""
		if not self.queue:
			return False

		player = self.queue.pop()
		player.volume = volume
		player.set(source)

		return True

	def destroy(self) -> None:
		"""
		Destroys all players contained in the SFXRing and
		renders it unusable.
		"""
		for player, hdlr in self.players:
			player.remove_handler("on_eos", hdlr)
			player.destroy()

		# Kinda unnecessary but i like me some good cleanup
		del self.players
		del self.queue
		del self.controller
