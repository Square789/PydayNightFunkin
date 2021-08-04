
import typing as t

from pyglet.image import ImageData, Texture

from pyday_night_funkin.asset_system import ASSETS
import pyday_night_funkin.constants as CNST
from pyday_night_funkin.image_loader import load_animation_frames_from_xml, load_image
from pyday_night_funkin.pnf_sprite import PNFSprite
from pyday_night_funkin.utils import clamp, to_rgba_bytes

if t.TYPE_CHECKING:
	from pyday_night_funkin.scenes import InGame


ICON_X_DISPLACEMENT = 124

class HealthBar():
	"""
	Class that registers and contains a few sprites to render a game's
	health bar with two icons to the screen.
	"""
	def __init__(
		self,
		scene: "InGame",
		camera: str,
		opponent_icon: str,
		player_icon: str,
		layers: t.Tuple[str, str, str],
		ded_icon_threshold: float = 0.2,
		opponent_color: t.Union[t.Tuple[int, int, int, int], int] = 0xFF0000FF,
		player_color: t.Union[t.Tuple[int, int, int, int], int] = 0x66FF33FF,
	) -> None:
		"""
		"""

		self.ded_icon_threshold = ded_icon_threshold

		bg_layer, bar_layer, icon_layer = layers

		bar_image = ASSETS.IMG.HEALTH_BAR.load()
		self.health_bar = scene.create_sprite(
			bg_layer,
			((CNST.GAME_WIDTH - bar_image.width) // 2, int(CNST.GAME_HEIGHT * 0.9)),
			bar_image,
			camera
		)

		bar_y = self.health_bar.world_y + 4
		self.opponent_bar = scene.create_sprite(
			bar_layer,
			(0, bar_y),
			self._create_bar_part(bar_image.height - 8, opponent_color),
			camera,
		)
		self.player_bar = scene.create_sprite(
			bar_layer,
			(0, bar_y),
			self._create_bar_part(bar_image.height - 8, player_color),
			camera,
		)

		healthbar_icons = ASSETS.XML.ICON_GRID.load()
		self.opponent_icons = [fi_tex.texture for fi_tex in healthbar_icons[opponent_icon]]
		self.player_icons = [fi_tex.texture for fi_tex in healthbar_icons[player_icon]]
		# This assumes all opponent and player icons are of same height (i mean, they are)
		icon_y = self.health_bar.world_y + (bar_image.height - self.opponent_icons[0].height) // 2
		self.opponent_sprite = scene.create_sprite(
			icon_layer, (0, icon_y), self.opponent_icons[0], camera
		)
		self.player_sprite = scene.create_sprite(
			icon_layer, (0, icon_y), self.player_icons[0], camera
		)
		self.player_sprite.world_scale_x = -1.0

	def _create_bar_part(self, height: int, color) -> Texture:
		return ImageData(1, height, "RGBA", to_rgba_bytes(color) * height).get_texture()

	def update(self, new_health: float) -> None:
		"""
		Updates the HealthBar with new_health, clamped to the range
		of 0..1. Bar size and icon position will be changed
		accordingly and icons will be changed to their ded state if
		below the health bar's ded threshold.
		"""
		bar_width = self.health_bar._texture.width - 8
		opponent_bar_x = self.health_bar.world_x + 4
		opponent_bar_width = int((1.0 - clamp(new_health, 0.0, 1.0)) * bar_width)
		player_bar_x = opponent_bar_x + opponent_bar_width
		player_bar_width = bar_width - opponent_bar_width

		self.opponent_bar.world_update(x = opponent_bar_x, scale_x = opponent_bar_width)
		self.player_bar.world_update(x = player_bar_x, scale_x = player_bar_width)
		self.opponent_sprite.world_x = player_bar_x - ICON_X_DISPLACEMENT
		self.player_sprite.world_x = player_bar_x + ICON_X_DISPLACEMENT

		if new_health > (1.0 - self.ded_icon_threshold):
			if self.opponent_sprite.image != self.opponent_icons[1]:
				self.opponent_sprite.image = self.opponent_icons[1]
		elif new_health < self.ded_icon_threshold:
			if self.player_sprite.image != self.player_icons[1]:
				self.player_sprite.image = self.player_icons[1]
		else:
			if self.player_sprite.image != self.player_icons[0]:
				self.player_sprite.image = self.player_icons[0]
			if self.opponent_sprite.image != self.opponent_icons[0]:
				self.opponent_sprite.image = self.opponent_icons[0]
