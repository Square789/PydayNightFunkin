
import typing as t

from pyday_night_funkin.asset_system import ASSET, load_asset
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin import scenes
from pyday_night_funkin.utils import to_rgb_tuple

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.main_game import Game 


class GameOverScene(scenes.MusicBeatScene):
	update_passthrough = False
	draw_passthrough = False

	def __init__(self, game: "Game", bf: "PNFSprite") -> None:
		super().__init__(game)
		self.conductor.bpm = 100

		self.game_over_music = load_asset(ASSET.MUSIC_GAME_OVER)
		self.game_over_end = load_asset(ASSET.MUSIC_GAME_OVER_END)

		self.is_ending = False

		self.bf = bf

		bg = self.create_object("bg", image=CNST.PIXEL_TEXTURE)
		bg.color = to_rgb_tuple(CNST.BLACK)
		bg.scale_x = CNST.GAME_WIDTH
		bg.scale_y = CNST.GAME_HEIGHT

		self.add(self.bf, "main", "main")
		self.bf.animation.play("game_over_ini")

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
			self.bf.animation.current_name == "game_over_ini" and
			self.bf.animation._frame_idx >= 12
		):
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
			self.remove_scene(False, True)

		self.clock.schedule_once(f, 2.7)
