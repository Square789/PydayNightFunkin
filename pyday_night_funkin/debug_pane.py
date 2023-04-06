
import queue

from pyglet import font

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.pnf_text import PNFText
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.superscene import SuperScene
from pyday_night_funkin.core.utils import to_rgba_tuple


class DebugPane(SuperScene):
	"""
	Shoddy class to manage text lines on a rectangle, used to display
	debug messages and fps.
	"""

	FONT_SIZE = 8
	FPS_FONT_SIZE = 12
	LINE_DIST = 2
	PADDING = 8

	def __init__(self, line_amount: int, message_queue: queue.Queue = None) -> None:
		super().__init__(CNST.GAME_WIDTH, CNST.GAME_HEIGHT)

		self.insert_index = 0
		self._line_amount = line_amount
		self._queue = message_queue

		self.background = PNFGroup(order=0)
		self.foreground = PNFGroup(order=1)
		self.batch = PNFBatch()
		self.labels = [
			PNFText(
				x = 10,
				y = (self.FONT_SIZE * i + self.LINE_DIST * i),
				font_name = "Consolas",
				font_size = self.FONT_SIZE,
				context = self.get_context(self.foreground),
			) for i in range(line_amount)
		]
		self.timing_label = PNFText(
			x = 10,
			y = ((self.FONT_SIZE * (line_amount + 1)) + 4 + self.LINE_DIST * line_amount),
			font_name = "Consolas",
			font_size = self.FPS_FONT_SIZE,
			multiline = True,
			context = self.get_context(self.foreground),
		)
		self.debug_rect = PNFSprite(
			x = self.PADDING,
			y = 0,
			context = self.get_context(self.background),
		)
		self.debug_rect.make_rect(
			to_rgba_tuple(0x2020AA64),
			CNST.GAME_WIDTH - 2 * self.PADDING,
			(self.FONT_SIZE * (line_amount + 1)) + (self.LINE_DIST * (line_amount - 1)),
		)

		# HACK getting the ascent like this
		bluegh = font.load("Consolas", self.FPS_FONT_SIZE).ascent
		self.fps_rect = PNFSprite(
			x = self.PADDING,
			y = self.timing_label.y - self.LINE_DIST,
			context = self.get_context(self.background),
		)
		self.fps_rect.make_rect(
			to_rgba_tuple(0x7F7F7F7F),
			CNST.GAME_WIDTH // 3,
			(bluegh * 4) + self.LINE_DIST * 2,
		)

	def update(self, timing_label_string: str = "") -> None:
		"""
		Updates the debug pane and writes all queued messages to
		the labels, causing a possibly overflowing label's text to be
		deleted and bumping up all other labels.
		Call this when GL allows it, there have been weird threading
		errors in the past.
		"""
		if timing_label_string:
			self.timing_label.text = timing_label_string

		if self._queue.empty():
			return

		while True:
			try:
				message = self._queue.get_nowait()
			except queue.Empty:
				break

			if self.insert_index == len(self.labels):
				self.insert_index -= 1
				for i in range(len(self.labels) - 1):
					self.labels[i].text = self.labels[i + 1].text

			self.labels[self.insert_index].text = message
			self.insert_index += 1
