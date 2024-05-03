
import typing as t

from pyday_night_funkin.core.asset_system import load_sound
from pyday_night_funkin.core.scene import SceneKernel
from pyday_night_funkin.enums import Control
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.main_game import Game


class GameOverScene(scenes.MusicBeatScene):
	def __init__(self, kernel: "SceneKernel", bf: "PNFSprite") -> None:
		super().__init__(kernel)

		self.update_passthrough = False
		self.draw_passthrough = False

		self.lyr_main = self.create_layer()

		self.main_camera = self.create_camera()

		self.conductor.bpm = 100

		self.game_over_music = load_sound("shared/music/gameOver.ogg")
		self.game_over_end = load_sound("shared/music/gameOverEnd.ogg")

		self.is_ending = False

		self.bf = bf

		self.add(bf, self.lyr_main, self.main_camera)
		bf.animation.play("game_over_ini")
		self._camera_locked_on = False

		self.sfx_ring.play(load_sound("shared/sounds/fnf_loss_sfx.ogg"))
		self.sync_conductor_from_player(self.game.player)

	@classmethod
	def get_kernel(cls, game: "Game", bf: "PNFSprite") -> SceneKernel:
		return SceneKernel(cls, game, bf)

	def update(self, dt: float) -> None:
		super().update(dt)

		if self.game.key_handler.just_pressed(Control.ENTER):
			self.retry()

		if self.game.key_handler.just_pressed(Control.BACK) and not self.is_ending:
			self.game.player.stop()
			self.remove_scene(end_game=True)

		if (
			not self._camera_locked_on and
			self.bf.animation.current_name == "game_over_ini" and
			self.bf.animation.get_current_frame_index() >= 12
		):
			self._camera_locked_on = True
			self.main_camera.set_follow_target(self.bf.get_midpoint(), 0.01)

		if (
			self.bf.animation.current_name == "game_over_ini" and
			not self.bf.animation.current.playing
		):
			self.game.player.set(self.game_over_music)
			self.bf.animation.play("game_over_loop")

	def retry(self) -> None:
		if self.is_ending:
			return

		self.is_ending = True
		self.bf.animation.play("game_over_end", True)
		self.game.player.set(self.game_over_end)

		def f(_):
			# Assumes the above scene is an InGame scene, so its
			# remove_subscene method will take `end_self`, `reset` as args.
			self.game.player.stop()
			self.remove_scene(end_game=False, reset=True)

		self.clock.schedule_once(f, 2.7)
