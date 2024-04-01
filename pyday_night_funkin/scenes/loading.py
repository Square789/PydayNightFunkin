
from time import perf_counter
import typing as t

from loguru import logger

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.asset_system import load_image
from pyday_night_funkin.core.scene import BaseScene, SceneKernel
from pyday_night_funkin.core.pnf_text import PNFText, TextAlignment
from pyday_night_funkin.core.utils import lerp
from pyday_night_funkin.enums import Control

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class LoadingKernel(SceneKernel):
	def __init__(
		self,
		scene_type: t.Type["LoadingScene"],
		game: "Game",
		target_kernel: SceneKernel,
	) -> None:
		super().__init__(scene_type, game, target_kernel)


class LoadingScene(BaseScene):
	def __init__(
		self,
		kernel: SceneKernel,
		target_kernel: SceneKernel,
	) -> None:
		kernel.fill(layers=("bg", "fg", "fg2"))

		super().__init__(kernel)

		self.target_kernel = target_kernel

		self.default_camera.clear_color = (0.792, 1.0, 0.302, 1.0)

		self.bg_image = self.create_object("bg", image=load_image("preload/images/funkay.png"))
		self.bg_image.set_scale_and_repos(CNST.GAME_HEIGHT / self.bg_image.get_current_frame_dimensions()[1])
		self.bg_image.screen_center(CNST.GAME_DIMENSIONS)

		self.loading_text = self.create_object(
			"fg2",
			object_class=PNFText,
			x = 10,
			y = CNST.GAME_HEIGHT - 28,
			font_size = 12,
			color = (0x07, 0x07, 0x00, 0xFF),
			font_name = "VCR OSD Mono",
			width = CNST.GAME_WIDTH - 20,
			align = TextAlignment.CENTER,
		)
		self.loading_bar = self.create_object("fg", x=10, y=CNST.GAME_HEIGHT - 28)
		self.loading_bar.make_rect((0xFF, 0x16, 0xD2, 0xFF), 2, 18)
		self.loading_bar.origin = self.loading_bar.origin[0] - 0.5, self.loading_bar.origin[1]

		self._started_exiting = False

		self._start_time = perf_counter()

		loading_request = self.target_kernel.get_loading_hints()
		self.loading_tracker = self.game.assets.start_threaded_load(loading_request)

	@classmethod
	def get_kernel(cls, game: "Game", target_kernel: SceneKernel) -> LoadingKernel:
		return LoadingKernel(cls, game, target_kernel)

	@classmethod
	def load_or_set(cls, game: "Game", target_kernel: SceneKernel):
		if game.assets.requires_loading_process(target_kernel.get_loading_hints()):
			game.set_scene(cls.get_kernel(game, target_kernel))
		else:
			game.set_scene(target_kernel)

	def update(self, dt: float) -> None:
		super().update(dt)

		self.bg_image.set_scale_and_repos(
			lerp(CNST.GAME_WIDTH * 0.88, self.bg_image.width, 0.9) /
			self.bg_image.get_current_frame_dimensions()[0]
		)
		if self.game.key_handler.just_pressed(Control.ENTER):
			self.bg_image.set_scale_and_repos(
				(self.bg_image.width + 60) / self.bg_image.get_current_frame_dimensions()[0]
			)

		loading_progress = self.loading_tracker.get_progress()

		if loading_progress.requested == 0:
			progress = 1.0
		else:
			progress = loading_progress.loaded / loading_progress.requested

		self.loading_text.text = (
			f"{loading_progress.loaded} / {loading_progress.requested}" +
			("" if loading_progress.requested_final else "+?") +
			(f" [{loading_progress.last_loaded}]" if loading_progress.last_loaded else "")
		)

		bar_width = progress * (CNST.GAME_WIDTH - 20)
		self.loading_bar.scale_x = lerp(self.loading_bar.scale_x, bar_width, 1.0 - 0.5**(dt * 10.0))

		if self.loading_tracker.is_done() and not self._started_exiting:
			logger.trace(f"Loading finished in {perf_counter() - self._start_time:>.4f}s")
			self._started_exiting = True
			self.game.set_scene(self.target_kernel)
