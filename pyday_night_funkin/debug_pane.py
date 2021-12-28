
from queue import Queue
import queue
import typing as t

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.context import Context
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.pnf_label import PNFLabel
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.utils import create_pixel


class DebugPane():
	"""
	Shoddy class to manage text lines on a rectangle, used to display
	debug messages and fps.
	"""

	FONT_SIZE = 8
	LINE_DIST = 2
	PADDING = 8

	def __init__(self, line_amount: int) -> None:
		# NOTE: This uses PNF graphics, but is not a scene,
		# so update, tweens and all other good stuff won't work.
		self.insert_index = 0
		self.background = PNFGroup(order = 0)
		self.foreground = PNFGroup(order = 1)
		self.batch = PNFBatch()
		self._queue = Queue()
		self.labels = [
			PNFLabel(
				"",
				font_name = "Consolas",
				font_size = self.FONT_SIZE,
				x = 10,
				y = (self.FONT_SIZE * i + self.LINE_DIST * i),
				context = Context(self.batch, self.foreground, None),
			) for i in range(line_amount)
		]
		self.fps_label = PNFLabel(
			"",
			font_name = "Consolas",
			font_size = self.FONT_SIZE + 4,
			x = 20,
			y = ((self.FONT_SIZE * (line_amount + 1)) + 4 + self.LINE_DIST * line_amount),
			context = Context(self.batch, self.foreground, None),
		)
		self.rect = PNFSprite(
			image = create_pixel(0x2020AAFF),
			x = self.PADDING,
			y = 0,
			context = Context(self.batch, self.background, None),
		)
		self.rect.scale_x = CNST.GAME_WIDTH - 2 * self.PADDING
		self.rect.scale_y = (self.FONT_SIZE * (line_amount + 1)) + (self.LINE_DIST * (line_amount - 1))

		self.rect.opacity = 100

	def add_message(self, log_message: str) -> None:
		"""
		Adds the given log message to the debug pane's queue.
		This should be thread-safe, but the change will only appear
		once `update` is called.
		"""
		self._queue.put(log_message)

	def update(
		self, fps: int, fts: float, pfts: float, draw_time: float, update_time: float
	) -> None:
		"""
		Updates the debug pane and writes all queued messages to
		the labels, causing a possibly overflowing label's text to be
		deleted and bumping up all other labels.
		Additionally, sets the fps label's text to a readable string
		built from the supplied fps, draw time and update time.
		Call this when GL allows it, there have been weird threading
		errors in the past.
		"""
		self.fps_label.text = (
			f"FPS: {fps:>4}; FT: AVG {fts:>4.1f}ms, MAX {pfts:>4.1f}ms; Frame time: "
			f"{draw_time + update_time:>5.1f}ms (Draw {draw_time:>5.1f}, "
			f"Update {update_time:>5.1f}) "
		)

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

	def draw(self):
		"""
		Draw the DebugPane.
		"""
		self.batch.draw()
