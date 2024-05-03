
import typing as t

from pyday_night_funkin.base_game_pack import fetch_character_icons
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.asset_system import load_image
from pyday_night_funkin.core.utils import clamp, to_rgba_tuple, get_pixel_tex

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.scene_container import SceneLayer
	from pyday_night_funkin.scenes import InGameScene


class HealthBar:
	"""
	Class that registers and contains a few sprites to render a game's
	health bar with two icons to the screen.
	"""
	def __init__(
		self,
		scene: "InGameScene",
		camera: "Camera",
		opponent_icon_name: str,
		player_icon_name: str,
		layer: "SceneLayer",
		ded_icon_threshold: float = 0.2,
		opponent_color: int = 0xFF0000FF,
		player_color: int = 0x66FF33FF,
	) -> None:
		self.ded_icon_threshold = ded_icon_threshold

		bar_image = load_image("shared/images/healthBar.png")
		self.background = scene.create_object(
			layer,
			camera,
			x = (CNST.GAME_WIDTH - bar_image.width) // 2,
			y = int(CNST.GAME_HEIGHT * 0.9),
			image = bar_image,
		)

		bar_y = self.background.y + 4
		self.opponent_bar = scene.create_object(layer, camera, y=bar_y, image=get_pixel_tex())
		self.opponent_bar.rgba = to_rgba_tuple(opponent_color)
		self.player_bar = scene.create_object(layer, camera, y=bar_y, image=get_pixel_tex())
		self.player_bar.rgba = to_rgba_tuple(player_color)
		self.opponent_bar.origin = self.player_bar.origin = (0, 0)
		self.opponent_bar.scale_y = self.player_bar.scale_y = bar_image.height - 8

		self.opponent_icons = fetch_character_icons(opponent_icon_name)
		self.player_icons = fetch_character_icons(player_icon_name)
		# This assumes all opponent and player icons are of same height and width
		# (Which they are, but hey)
		icon_y = self.background.y + (bar_image.height - self.opponent_icons[0].height) // 2
		self.opponent_sprite = scene.create_object(
			layer, camera, x=0, y=icon_y, image=self.opponent_icons[0]
		)
		self.player_sprite = scene.create_object(
			layer, camera, x=0, y=icon_y, image=self.player_icons[0]
		)
		self.player_sprite.flip_x = True

	def update(self, new_health: float) -> None:
		"""
		Updates the HealthBar with new_health, clamped to the range
		of 0..1. Bar size and icon position will be changed
		accordingly and icons will be changed to their ded state if
		below the health bar's ded threshold.
		"""
		bar_width = self.background._texture.width - 8
		opponent_bar_x = self.background.x + 4
		opponent_bar_width = int((1.0 - clamp(new_health, 0.0, 1.0)) * bar_width)
		player_bar_x = opponent_bar_x + opponent_bar_width

		self.opponent_bar.x = opponent_bar_x
		self.opponent_bar.scale_x = opponent_bar_width
		self.player_bar.x = player_bar_x
		self.player_bar.scale_x = bar_width - opponent_bar_width

		self.player_sprite.x = player_bar_x - 26
		self.opponent_sprite.x = player_bar_x - (self.opponent_sprite.width - 26)

		if new_health > (1.0 - self.ded_icon_threshold):
			self.opponent_sprite.image = self.opponent_icons[1]
		elif new_health < self.ded_icon_threshold:
			self.player_sprite.image = self.player_icons[1]
		else:
			self.player_sprite.image = self.player_icons[0]
			self.opponent_sprite.image = self.opponent_icons[0]
