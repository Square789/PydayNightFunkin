
import typing as t

from pyglet.image import ImageData, Texture
from pyglet.shapes import Rectangle

from pyday_night_funkin.image_loader import load_animation_frames_from_xml, load_image
from pyday_night_funkin.pnf_sprite import PNFSprite
from pyday_night_funkin.utils import to_rgba_bytes

if t.TYPE_CHECKING:
	from pathlib import Path

	import pyday_night_funkin.constants as CNST
	from pyday_night_funkin.scenes import InGame


class HealthBar(PNFSprite):
	def __init__(
		self,
		scene: "InGame",
		camera: str,
		opponent_color: t.Union[t.Tuple[int, int, int, int], int],
		player_color: t.Union[t.Tuple[int, int, int, int], int],
		opponent_icon: str,
		player_icon: str,
		*args,
		**kwargs,
	) -> None:

		self._health = 1.0

		bar_image = load_image(CNST.ASSETS / "shared/images/healthBar.png")

		opponent_part_filler = self._create_bar_part(bar_image.height - 8, opponent_color)
		player_part_filler = self._create_bar_part(bar_image.height - 8, player_color)

		healthbar_icons = load_animation_frames_from_xml(CNST.ASSETS / "images/iconGrid.xml")
		opponent_icons = healthbar_icons[opponent_icon]
		player_icons = healthbar_icons[player_icon]


		super().__init__(
			bar_image,
			(CNST.GAME_WIDTH - bar_image.width) // 2,
			int(CNST.GAME_HEIGHT * 0.9),
			*args,
			**kwargs
		)
		scene.register_sprite(self, camera)

	def _create_bar_part(self, height: int, color) -> Texture:
		return ImageData(1, height, "RGBA", to_rgba_bytes(color) * height).get_texture()

	@property
	def health(self) -> float:
		return self._health

	@health.setter
	def health(self, new_health: float) -> None:
		self._health = new_health
		# TODO update
