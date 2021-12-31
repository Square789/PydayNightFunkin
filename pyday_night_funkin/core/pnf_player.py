
from pyglet.media import Player


class PNFPlayer(Player):
	def set(self, source) -> None:
		"""
		Stops all running playbacks, clears the playlist and
		immediatedly causes the player to start playing the newly
		supplied source.
		"""
		# NOTE: Legit no clue how bad of an idea this is, but works :TM:
		while self._playlists:
			self.next_source()
		self.queue(source)
		self._set_playing(True)
