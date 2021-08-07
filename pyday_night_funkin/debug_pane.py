
import typing as t

from collections import deque

import pyglet
if pyglet.version.startswith("2.0"):
	from pyglet.graphics import Group
	OrderedGroup = lambda o, parent = None: Group(o, parent)
else:
	from pyglet.graphics import OrderedGroup
from pyglet.shapes import Rectangle
from pyglet.text import Label

import pyday_night_funkin.constants as CNST

if t.TYPE_CHECKING:
	from pyglet.graphics import Batch


class DebugPane():
	"""
	Shoddy class to manage text lines on a rectangle, used to display
	debug messages and fps.
	"""

	FONT_SIZE = 8
	LINE_DIST = 2
	PADDING = 8

	def __init__(self, line_amount: int, batch: "Batch") -> None:
		self.insert_index = 0
		self.background = OrderedGroup(0)
		self.foreground = OrderedGroup(1)
		self.batch = batch
		self.labels = [
			Label(
				"",
				font_name = "Consolas",
				font_size = self.FONT_SIZE,
				x = 10,
				y = CNST.GAME_HEIGHT - (self.FONT_SIZE * (i + 1) + self.LINE_DIST * i),
				batch = batch,
				group = self.foreground,
			) for i in range(line_amount)
		]
		self.fps_label = Label(
			"",
			font_name = "Consolas",
			font_size = self.FONT_SIZE + 4,
			x = 20,
			y = CNST.GAME_HEIGHT - \
				((self.FONT_SIZE * (line_amount + 1)) + 4 + self.LINE_DIST * line_amount),
			batch = batch,
			group = self.foreground,
		)
		self.rect = Rectangle(
			self.PADDING,
			CNST.GAME_HEIGHT - (self.FONT_SIZE * line_amount) - \
				(self.LINE_DIST * (line_amount - 1)),
			CNST.GAME_WIDTH - 2 * self.PADDING,
			(self.FONT_SIZE * line_amount) + (self.LINE_DIST * (line_amount - 1)),
			color = (20, 20, 100),
			batch = batch,
			group = self.background,
		)
		self.rect.opacity = 100

	def add_message(self, log_message: str) -> None:
		"""
		Adds the given log message to the debug pane, causing a
		possibly overflowing label's text to be deleted and bumping
		up all other labels.
		"""
		if self.insert_index == len(self.labels):
			self.insert_index -= 1
			for i in range(len(self.labels) - 1):
				self.labels[i].text = self.labels[i + 1].text

		self.labels[self.insert_index].text = log_message
		self.insert_index += 1

	def update_fps_label(self, fps: int, draw_time: float):
		"""
		Sets the fps label's text to a readable string built from the
		supplied fps and draw time.
		Does not redraw the label.
		"""
		self.fps_label.text = f"FPS: {fps:>4}; Draw time: {draw_time:.1f} ms"
