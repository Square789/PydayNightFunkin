
import typing as t

from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.enums import CONTROL
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.main_game import Game 


class GameOverScene(scenes.MusicBeatScene):

	def __init__(self, game: "Game", bf: "PNFSprite") -> None:
		super().__init__(game)
		self.update_passthrough = False
		self.draw_passthrough = False

		self.conductor.bpm = 100

		self.game_over_music = load_asset(ASSET.MUSIC_GAME_OVER)
		self.game_over_end = load_asset(ASSET.MUSIC_GAME_OVER_END)

		self.is_ending = False

		self.bf = bf

		self.add(self.bf, "main", "main")
		self.bf.animation.play("game_over_ini")
		self._camera_locked_on = False

		self.sfx_ring.play(load_asset(ASSET.SOUND_LOSS))

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ("main",)

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("bg", "main")

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(CONTROL.ENTER):
			self.end()

		if self.game.key_handler.just_pressed(CONTROL.BACK) and not self.is_ending:
			self.remove_scene(True)

		if (
			not self._camera_locked_on and
			self.bf.animation.current_name == "game_over_ini" and
			self.bf.animation._frame_idx >= 12
		):
			self._camera_locked_on = True
			self.cameras["main"].set_follow_target(self.bf.get_midpoint(), 0.01)

		if self.bf.animation.current_name == "game_over_ini" and not self.bf.animation.playing:
			self.game.player.set(self.game_over_music)
			self.bf.animation.play("game_over_loop")

		if self.game.player.playing:
			# TODO 5 IQ song tracking once again
			self.conductor.song_position = self.game.player.time

	def end(self) -> None:
		if self.is_ending:
			return

		self.is_ending = True
		self.bf.animation.play("game_over_confirm", True)
		self.game.player.set(self.game_over_end)

		def f(_):
			# Assumes the above scene is an InGame scene, so its
			# remove_subscene method will take `end_self`, `reset` as args.
			self.remove_scene(False, True)

		self.clock.schedule_once(f, 2.7)
