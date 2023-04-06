
from enum import IntEnum
import typing as t

from pyglet.image import ImageData, Texture

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.camera import SimpleCamera
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.superscene import SuperScene


_DOT = ord('.')
_ICON_BITMAP = b"".join(
	b"\x00\x00\x00\x00" if v == _DOT else b"\xFF\xFF\xFF\xFF" for v in (
		b"........#.###..."
		b".......##....#.."
		b"......###.##..#."
		b".....####...#..#"
		b"....#####.#..#.#"
		b".########..#.#.#"
		b"#########..#.#.#"
		b"#########..#.#.#"
		b"#########..#.#.#"
		b"#########..#.#.#"
		b".########..#.#.#"
		b"....#####.#..#.#"
		b".....####...#..#"
		b"......###.##..#."
		b".......##....#.."
		b"........#.###..."
	)
)

_BOX_SIZE = 12
_HEIGHT = 32

class _VolumeControlState(IntEnum):
	HIDDEN = 0
	SHOWN = 1
	HIDING = 2


class VolumeControlDropdown(SuperScene):
	def __init__(self, granularity: int) -> None:
		super().__init__(CNST.GAME_WIDTH, CNST.GAME_HEIGHT)

		self.granularity = granularity
		self._state = _VolumeControlState.HIDDEN
		self._state_progress = 0.0

		self._boxes: t.List[PNFSprite] = []
		self._camera = SimpleCamera(CNST.GAME_WIDTH, CNST.GAME_HEIGHT)
		self._cameras = (self._camera,)

		self.batch = PNFBatch()

		bg_group = PNFGroup(order=0)
		fg_group = PNFGroup(order=1)

		width = (8 + 16 + 8 + self.granularity * _BOX_SIZE + (self.granularity - 1) * 4 + 8)
		background_rect = PNFSprite(context=self.get_context(bg_group))
		background_rect.make_rect((0x20, 0x20, 0x20, 0x7F), width, _HEIGHT)

		self.icon = PNFSprite(
			ImageData(16, 16, ("RGBA"), _ICON_BITMAP).create_texture(Texture),
			8,
			(_HEIGHT - 16) // 2,
			context = self.get_context(fg_group),
		)
		for i in range(self.granularity):
			box = PNFSprite(
				x = 8 + 16 + 8 + i * (_BOX_SIZE + 4),
				y = (_HEIGHT - _BOX_SIZE) // 2,
				context = self.get_context(fg_group),
			)
			box.make_rect((0xFF, 0xFF, 0xFF, 0xFF), _BOX_SIZE, _BOX_SIZE)
			self._boxes.append(box)

		shift = (CNST.GAME_WIDTH - width) // 2
		self._camera.x -= shift

	def update(self, dt: float) -> None:
		if self._state is _VolumeControlState.HIDDEN:
			return

		self._state_progress -= dt

		while True:
			if self._state is _VolumeControlState.HIDING:
				if self._state_progress <= 0.0:
					self._state = _VolumeControlState.HIDDEN
					return
				self._camera.y = (1.0 - self._state_progress / 0.3) * _HEIGHT
				return

			elif self._state is _VolumeControlState.SHOWN:
				if self._state_progress <= 0.0:
					self._state = _VolumeControlState.HIDING
					self._state_progress += 0.3
					continue
				else:
					return

			break

	def display_change(self, step: int, dont_show: bool = False) -> None:
		"""
		Displays change to the volume dropdown by coloring all boxes
		up to `step`. Will arrange for the dropdown to be drawn by
		setting the show state appropiately, unless `dont_show` is set
		to `True`.
		"""
		for i, box in enumerate(self._boxes):
			box.opacity = 0xFF if step > i else 0x20

		if not dont_show:
			self._state = _VolumeControlState.SHOWN
			self._state_progress = 1.0
			self._camera.y = 0.0

	def draw(self):
		"""
		Draws the VolumeControl if applicable.
		"""
		if self._state is not _VolumeControlState.HIDDEN:
			self.batch.draw(self._camera)
