
from enum import IntEnum
from loguru import logger
import typing as t

from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.core.scene import BaseScene, SceneKernel
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.sound import PNFPlayer



class ConductorSyncMode(IntEnum):
	DT = 0
	PLAYER = 1


class MusicBeatScene(BaseScene):
	"""
	A core scene for pretty much all of FNF/PNFs menus and the game.
	The music beat scene offers the two functions `on_beat_hit` and
	`on_step_hit` that are called from `update` every time the scene's
	conductor's beat/step respectively change, so stuff can happen in
	tune to music.
	Skipped beats and skipped steps will be accustomed, so multiple
	successive calls in the same frame are possible.
	"""

	def __init__(self, kernel: SceneKernel) -> None:
		super().__init__(kernel.fill(transition=scenes.FNFTransitionScene))

		self.conductor = Conductor()
		self._conductor_sync_mode: t.Optional[ConductorSyncMode] = None
		self._conductor_sync_target: t.Optional["PNFPlayer"] = None
		self._sync_conductor_when_paused: bool = False
		self._stop_conductor_sync_on_eos: bool = False
		self._reset_step_on_conductor_sync_eos: bool = True

		self._last_step: int = -1
		self.cur_step: int = -1
		self.cur_beat: int = -1

	def sync_conductor_from_player(
		self,
		player: "PNFPlayer",
		sync_when_paused: bool = False,
		stop_on_eos: bool = False,
		reset_step_on_eos: bool = True,
	) -> None:
		"""
		Starts syncing the scene's conductor from a player.
		:param player: The player whose play time to target.
		:param sync_when_paused: Whether to sync when the player is
		paused.
		:param stop_on_eos: Whether to automatically stop syncing once
		the player exhausted its current source.
		:param reset_step_on_eos: Whether to reset the scene's step
		once the player exhausted its current source.
		"""
		self.stop_conductor_syncing()
		self._conductor_sync_mode = ConductorSyncMode.PLAYER
		self._conductor_sync_target = player
		self._sync_conductor_when_paused = sync_when_paused
		self._stop_conductor_sync_on_eos = stop_on_eos
		self._reset_step_on_conductor_sync_eos = reset_step_on_eos
		player.set_handler("on_eos", self._conductor_sync_on_player_eos)

	def sync_conductor_from_dt(self) -> None:
		"""
		Starts syncing the scene's conductor from the `update`
		function's time delta.
		"""
		self.stop_conductor_syncing()
		self._conductor_sync_mode = ConductorSyncMode.DT

	def stop_conductor_syncing(self) -> None:
		"""
		Stops syncing the scene's conductor. Does nothing if it wasn't
		being synced in the first place.
		"""
		if self._conductor_sync_mode is ConductorSyncMode.PLAYER:
			self._conductor_sync_target.remove_handler("on_eos", self._conductor_sync_on_player_eos)
			self._conductor_sync_target = None

		self._conductor_sync_mode = None

	def _conductor_sync_on_player_eos(self) -> None:
		"""
		Conductor syncing helper method from the `MusicBeatScene`.
		Act like it doesn't exist if you don't know exactly what
		you're doing.
		"""
		# I hope to god this method isn't ever called during an update call somehow,
		# but from skimming the pyglet source, it shouldn't be.
		if self._reset_step_on_conductor_sync_eos:
			self._last_step = -1
			self.cur_step = -1
		if self._stop_conductor_sync_on_eos:
			self.stop_conductor_syncing()

	def update(self, dt: float) -> None:
		super().update(dt)

		if self._conductor_sync_mode is not None:
			if self._conductor_sync_mode is ConductorSyncMode.DT:
				self.conductor.song_position += dt * 1000.0
			elif (
				self._conductor_sync_mode is ConductorSyncMode.PLAYER and
				(self._sync_conductor_when_paused or self._conductor_sync_target.playing)
			):
				self.conductor.song_position = self._conductor_sync_target.time * 1000.0

		new_step = self.conductor.get_current_step()
		for tween_step in range(self.cur_step + 1, new_step + 1):
			if tween_step != self._last_step + 1:
				logger.warning(
					f"New step ({tween_step}) was not strictly 1 higher than "
					f"last step ({self._last_step})!"
				)
			self.cur_step = tween_step
			self.cur_beat = tween_step // 4
			self.on_step_hit()
			self._last_step = tween_step

	def on_beat_hit(self) -> None:
		"""
		This function is called from `on_step_hit` each 4th step.
		The current beat will be available in `self.cur_beat`.
		"""
		pass

	def on_step_hit(self) -> None:
		"""
		This function is called from `update` each step.
		The current step will be available in `self.cur_step`.
		"""
		if self.cur_step % 4 == 0:
			self.on_beat_hit()

	def destroy(self) -> None:
		super().destroy()
		self.stop_conductor_syncing()
