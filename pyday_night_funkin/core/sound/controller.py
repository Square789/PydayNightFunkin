
import typing as t

from loguru import logger

from .pnf_player import PNFPlayer
from .sfx_ring import SFXRing
from pyday_night_funkin.core.utils import clamp


_SFX_RING_DEFAULT_SIZE = 5

class SoundController:
	"""
	A necessary evil for keeping track of all players in a game so
	global volume regulation can be possible.
	Can set volume directly or from a list of predefined steps.
	"""

	def __init__(self, volume_steps: int) -> None:
		if volume_steps < 1:
			raise ValueError("Must have at least one volume step!")

		self._volume_steps = [i / volume_steps for i in range(volume_steps + 1)]
		self.selected_volume = volume_steps
		self.volume = 1.0
		self._known_players: t.List["PNFPlayer"] = []

	def create_sfx_ring(self, size: int = _SFX_RING_DEFAULT_SIZE) -> "SFXRing":
		"""
		Creates a new SFXRing from players created through this
		controller.
		"""
		ring = SFXRing(self, [self.create_player() for _ in range(size)])
		return ring

	def create_player(self) -> "PNFPlayer":
		"""
		Creates a new player, introducing it to this sound
		controller.
		"""
		player = PNFPlayer(self)
		self._known_players.append(player)
		return player

	def remove_player(self, player: "PNFPlayer") -> None:
		try:
			self._known_players.remove(player)
		except ValueError:
			logger.warning("PlayerController told to delete unknown player.")

	def change_volume(self, by: int) -> bool:
		"""
		Changes volume by one of the predefined volume steps.
		Clamps when out of bounds.
		"""
		new = clamp(self.selected_volume + by, 0, len(self._volume_steps) - 1)
		if new == self.selected_volume:
			return False

		self.set_volume_direct(self._volume_steps[new])
		self.selected_volume = new
		return True

	def set_volume_direct(self, new_volume: float) -> None:
		"""
		Directly sets the global game volume.
		Does not have any effect on the predefined volume steps.
		"""
		self.volume = new_volume
		for player in self._known_players:
			# They're linked to this controller and will read `self.volume` via this.
			player.volume = player.volume
