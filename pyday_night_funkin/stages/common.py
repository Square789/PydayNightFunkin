"""
Contains some functions to create/deliver things that keep appearing
in multiple levels.
"""

import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.asset_system import load_image
from pyday_night_funkin.core.scene import OrderedLayer
from pyday_night_funkin.note_handler import AbstractNoteHandler, NoteHandler
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.scenes.in_game import (
	Anchor, AnchorAlignment as Al, InGameScene, InGameSceneKernel
)


class BaseGameBaseStage(InGameScene):
	"""
	Common superclass for the base game's stages.
	Does stuff that stays uniform in the base game's stages.
	"""

	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				layers = (
					"background0", "background1", "girlfriend", "stage", "curtains",
					OrderedLayer("ui_combo"), "ui_arrows", "ui_notes", "ui0", "ui1", "ui2"
				),
				default_cam_zoom = 0.9,
				# Was (770, 450), bf's height added
				player_anchor = Anchor(Vec2(770, 885), Al.BOTTOM_LEFT, "stage"),
				# Was (400, 130), gf's height added
				girlfriend_anchor = Anchor(Vec2(400, 787), Al.BOTTOM_LEFT, "girlfriend"),
				# Was (100, 100), dad's dimensions added
				opponent_anchor = Anchor(Vec2(570, 835), Al.BOTTOM_RIGHT, "stage"),
			),
			*args,
			**kwargs,
		)

	def create_hud(self) -> HUD:
		return HUD(self, "hud", "ui", "ui_arrows", ("ui0", "ui1", "ui2"), "ui_combo")

	def create_note_handler(self) -> AbstractNoteHandler:
		return NoteHandler(self, "ui_notes", "hud")

	def spawn_default_base_game_arena(self) -> None:
		"""
		Sets up the classic default stage in this scene.
		To be exact, will create:
		- Stageback in layer `background0`
		- Stagefront in layer `background1`
		- Curtains in layer `curtains`
		"""
		stageback = self.create_object(
			"background0", "main", x=-600, y=-200, image=load_image("shared/images/stageback.png")
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.create_object(
			"background1", "main", x=-650, y=600, image=load_image("shared/images/stagefront.png")
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.set_scale_and_repos(1.1)

		stagecurtains = self.create_object(
			"curtains", "main", x=-500, y=-300, image=load_image("shared/images/stagecurtains.png")
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.set_scale_and_repos(.9)
