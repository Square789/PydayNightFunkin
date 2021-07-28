
import typing as t

from collections import deque

from pyglet.graphics import OrderedGroup
from pyglet.shapes import Rectangle
from pyglet.text import Label

import pyday_night_funkin.constants as CNST

if t.TYPE_CHECKING:
	from pyglet.graphics import Batch


class DebugPane():
	"""
	Shoddy class to manage text lines on a rectangle, used to display
	debug messages.
	"""

	FONT_SIZE = 8
	LINE_DIST = 2
	PADDING = 8

	def __init__(self, line_amount: int, batch: "Batch"):
		self.lineamt = line_amount
		self.labels = deque([], self.lineamt)
		self.background = OrderedGroup(0)
		self.foreground = OrderedGroup(1)
		self.batch = batch
		self.rect = Rectangle(
			self.PADDING,
			CNST.GAME_HEIGHT - (self.FONT_SIZE*self.lineamt) - (self.LINE_DIST*(self.lineamt - 1)),
			CNST.GAME_WIDTH - 2*self.PADDING,
			(self.FONT_SIZE*self.lineamt) + (self.LINE_DIST*(self.lineamt - 1)),
			color = (20, 20, 200),
			batch = batch,
			group = self.background,
		)
		self.rect.opacity = 100

	def add_message(self, log_message: str) -> None:
		"""
		Adds the given log message to the debug pane, causing a
		possibly overflowing label to be deleted and bumping up all
		other labels.
		"""
		full_before = False
		if len(self.labels) == self.lineamt:
			full_before = True
			self.labels[0].delete()
		x = Label(
			log_message,
			font_name = "Consolas",
			font_size = 8,
			color = CNST.WHITE,
			x = 10,
			y = CNST.GAME_HEIGHT - (
				self.FONT_SIZE*(len(self.labels) + 1) +
				self.LINE_DIST*len(self.labels)
			),
			batch = self.batch,
			group = self.foreground,
		)
		self.labels.append(x)
		if len(self.labels) == self.lineamt and full_before:
			for lbl in self.labels:
				lbl.y += self.FONT_SIZE + self.LINE_DIST
