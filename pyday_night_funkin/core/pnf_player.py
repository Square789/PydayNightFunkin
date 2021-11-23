
from pyglet.media import Player


class PNFPlayer(Player):
	def set(self, source) -> None:
		"""
		Stops all running playbacks, clears the playlist and
		immediatedly causes the player to start playing the newly
		supplied source.
		"""
		self._set_playing(False)
		self._playlists.clear()
		self.next_source()
		self.queue(source)
		self._set_playing(True)
