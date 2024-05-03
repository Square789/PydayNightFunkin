"""
Contains some functions to create/deliver things that keep appearing
in multiple levels.
"""

import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.asset_system import load_image
from pyday_night_funkin.note_handler import AbstractNoteHandler, NoteHandler
from pyday_night_funkin.hud import HUD
from pyday_night_funkin.scenes.in_game import (
	Anchor, AnchorAlignment as Al, InGameScene, InGameSceneKernel
)

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.scene_container import SceneLayer


class BaseGameBaseStage(InGameScene):
	"""
	Common superclass for the base game's stages.
	Does stuff that stays uniform in the base game's stages.
	"""

	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				default_cam_zoom = 0.9,
				# Was (770, 450), bf's height added
				player_anchor = Anchor(Vec2(770, 885), Al.BOTTOM_LEFT),
				# Was (400, 130), gf's height added
				girlfriend_anchor = Anchor(Vec2(400, 787), Al.BOTTOM_LEFT),
				# Was (100, 100), dad's dimensions added
				opponent_anchor = Anchor(Vec2(570, 835), Al.BOTTOM_RIGHT),
			),
			*args,
			**kwargs,
		)

		self.lyr_background = self.create_layer(True)
		"""
		A generic ordered layer for all things that go into the
		background of a scene/stage.
		"""

		self.lyr_girlfriend = self.create_layer()
		"""
		A layer supposed to be used for girlfriend. Unordered.
		"""

		self.lyr_stage = self.create_layer()
		"""
		A generic layer to be used for the main battling characters.
		Unordered.
		"""

		self.lyr_foreground = self.create_layer(True)
		"""
		A generic ordered layer for all things in the foreground of a
		scene/stage.

		This layer is in front of the stage.
		"""

		self.lyr_ui = self.create_layer(True)
		"""
		An ordered layer intended as the root of all UI elements.
		"""

	def create_hud(self) -> HUD:
		return HUD(self, self.hud_cam, self.lyr_ui)

	def create_note_handler(self) -> AbstractNoteHandler:
		# TODO: Weird coupling of notehandler and HUD, it shouldn't be
		# controlling notes directly in the first place.
		return NoteHandler(self, self.hud.get_note_layer(), self.hud_cam)

	def get_character_scene_parameters(self) -> t.Tuple[
		t.Tuple[t.Optional["SceneLayer"], t.Optional[t.Union[t.Iterable["Camera"], "Camera"]]],
		t.Tuple[t.Optional["SceneLayer"], t.Optional[t.Union[t.Iterable["Camera"], "Camera"]]],
		t.Tuple[t.Optional["SceneLayer"], t.Optional[t.Union[t.Iterable["Camera"], "Camera"]]],
	]:
		return (
			(self.lyr_stage, self.main_cam),
			(self.lyr_girlfriend, self.main_cam),
			(self.lyr_stage, self.main_cam),
		)

	def spawn_default_base_game_arena(self) -> None:
		"""
		Sets up the classic default stage in this scene.
		To be exact, will create:
		- Stage back and stage front in layer ``self.lyr_background``
		- Curtains in layer ``self.lyr_foreground
		"""
		stageback = self.create_object(
			self.lyr_background, x=-600, y=-200, image=load_image("shared/images/stageback.png")
		)
		stageback.scroll_factor = (.9, .9)
		stagefront = self.create_object(
			self.lyr_background, x=-650, y=600, image=load_image("shared/images/stagefront.png")
		)
		stagefront.scroll_factor = (.9, .9)
		stagefront.set_scale_and_repos(1.1)

		stagecurtains = self.create_object(
			self.lyr_foreground,
			x = -500,
			y = -300,
			image = load_image("shared/images/stagecurtains.png"),
		)
		stagecurtains.scroll_factor = (1.3, 1.3)
		stagecurtains.set_scale_and_repos(.9)
