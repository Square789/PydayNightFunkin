
from pyglet.math import Vec2

from pyday_night_funkin.core.asset_system import load_frames, load_image, load_sound
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.tween_effects.eases import in_out_quad
from pyday_night_funkin.scenes.in_game import (
	Anchor, AnchorAlignment as Al, DancerInfo, GameState, InGameSceneKernel
)
from pyday_night_funkin.stages.common import BaseGameBaseStage


class Week5Stage(BaseGameBaseStage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				default_cam_zoom = 0.8,
				player_anchor = Anchor(Vec2(970, 450 + 421), Al.BOTTOM_LEFT),
				# Was (400, 130), christmas gf's height added
				girlfriend_anchor = Anchor(Vec2(400, 130), Al.TOP_LEFT),
				# (-400, 400) + parent's dimensions
				opponent_anchor = Anchor(Vec2(-400 + 884, 100 + 782), Al.BOTTOM_RIGHT),
			),
			*args,
			**kwargs,
		)

		bg = self.create_object(
			self.lyr_background, image=load_image("week5/images/christmas/bgWalls.png")
		)
		bg.position = (-1000, -500)
		bg.scroll_factor = (0.2, 0.2)
		bg.set_scale_and_repos(0.8)

		self.toppers = self.create_object(self.lyr_background, x=-240, y=-90)
		self.toppers.frames = load_frames("week5/images/christmas/upperBop.xml")
		self.toppers.animation.add_by_prefix("bop", "Upper Crowd Bob", loop=False)
		self.toppers.scroll_factor = (0.33, 0.33)
		self.toppers.set_scale_and_repos(0.85)

		escalator = self.create_object(
			self.lyr_background,
			x = -1100,
			y = -600,
			image = load_image("week5/images/christmas/bgEscalator.png"),
		)
		escalator.scroll_factor = (0.3, 0.3)
		escalator.set_scale_and_repos(0.9)

		tree = self.create_object(
			self.lyr_background,
			x = 370,
			y = -250,
			image = load_image("week5/images/christmas/christmasTree.png"),
		)
		tree.scroll_factor = (0.4, 0.4)

		self.botters = self.create_object(self.lyr_background, x=-300, y=140)
		self.botters.frames = load_frames("week5/images/christmas/bottomBop.xml")
		self.botters.animation.add_by_prefix("bop", "Bottom Level Boppers", loop=False)
		self.botters.scroll_factor = (0.9, 0.9)

		self.create_object(
			self.lyr_background,
			x = -600,
			y = 700,
			image = load_image("week5/images/christmas/fgSnow.png"),
		)

		self.santa = self.create_object(self.lyr_background, x=-840, y=150)
		self.santa.frames = load_frames("week5/images/christmas/santa.xml")
		self.santa.animation.add_by_prefix("idle", "santa idle in fear", loop=False)

	def init_basic_fnf_stuff(self) -> None:
		super().init_basic_fnf_stuff()
		self.focus_targets[1].additional_offset = Vec2(0, -200)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		self.toppers.animation.play("bop")
		self.botters.animation.play("bop")
		self.santa.animation.play("idle")


class EggnogStage(Week5Stage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(kernel, *args, **kwargs)

		self.lyr_obscure = self.create_layer()

		self._lights_off_sound = load_sound("shared/sounds/Lights_Shut_off.ogg")

	def on_song_end(self) -> None:
		if self.in_story_mode:
			self.main_cam.visible = self.hud_cam.visible = False
			self.game.sfx_ring.play(self._lights_off_sound)

		super().on_song_end()


class WinterHorrorlandStage(BaseGameBaseStage):
	_watched_cutscene = False
	"""
	Whether we watched the cutscene. Stored on the class, which
	is ugly, but what can you do.
	"""

	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		super().__init__(
			kernel.fill(
				default_cam_zoom = 1.05,
				player_anchor = Anchor(Vec2(1090, 450 + 421), Al.BOTTOM_LEFT),
				# Was (400, 130), gf's height added
				girlfriend_anchor = Anchor(Vec2(400, 130), Al.TOP_LEFT),
				# monster's dimensions hardcoded in
				opponent_anchor = Anchor(Vec2(100 + 381, 150 + 719), Al.BOTTOM_RIGHT),
			),
			*args,
			**kwargs,
		)

		self.do_focus = False

		self.lyr_obscure = self.create_layer()

		self._lights_on_sound = load_sound("shared/sounds/Lights_Turn_On.ogg")

		bg = self.create_object(
			self.lyr_background, image=load_image("week5/images/christmas/evilBG.png")
		)
		bg.position = (-400, -500)
		bg.scroll_factor = (0.2, 0.2)
		bg.set_scale_and_repos(0.8)

		evil_tree = self.create_object(
			self.lyr_background,
			x = 300,
			y = -300,
			image = load_image("week5/images/christmas/evilTree.png"),
		)
		evil_tree.scroll_factor = (0.2, 0.2)

		self.create_object(
			self.lyr_background,
			x = -200,
			y = 700,
			image = load_image("week5/images/christmas/evilSnow.png"),
		)

	def ready(self) -> None:
		if not self.in_story_mode or WinterHorrorlandStage._watched_cutscene:
			super().ready()
			return

		WinterHorrorlandStage._watched_cutscene = True

		blackscreen = self.create_object(self.lyr_obscure, x=0, y=0)
		blackscreen.make_rect((0, 0, 0, 255), *self.game.dimensions)
		self.hud_cam.visible = False

		def _reveal_hud(_):
			self.hud_cam.visible = True
			self.effects.tween(
				self.main_cam,
				{"zoom": self._default_cam_zoom},
				2.5,
				in_out_quad,
				lambda _: self.start_countdown(),
			)

		def _spooky(_):
			self.remove(blackscreen)
			self.sfx_ring.play(self._lights_on_sound)
			# NOTE: Copypaste from overridden `ready`, yuck
			self.main_cam.look_at(
				self.opponent.get_current_frame_dimensions() * 0.5 +
				Vec2(100.0, 100.0) +
				Vec2(200.0, -2050.0)
			)
			self.main_cam.zoom = 1.5

			self.clock.schedule_once(_reveal_hud, 0.8)

		self.clock.schedule_once(_spooky, 0.1)

	def on_song_end(self) -> None:
		WinterHorrorlandStage._watched_cutscene = False
		super().on_song_end()

	def start_countdown(self) -> None:
		self.do_focus = True
		super().start_countdown()
