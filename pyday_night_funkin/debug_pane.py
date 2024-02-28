
import ctypes
import queue
import typing as t

from pyglet import font
from pyglet.gl import gl

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.core.graphics import PNFBatch, PNFGroup
from pyday_night_funkin.core.graphics.shared import GL_TYPE_SIZES
from pyday_night_funkin.core.graphics.vertexbuffer import BufferObject, RAMBackedBufferObject
from pyday_night_funkin.core.pnf_text import PNFText
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.shaders import ShaderContainer
from pyday_night_funkin.core.superscene import SuperScene
from pyday_night_funkin.core.utils import to_rgba_tuple, clamp


TIMING_GRAPH_QUAD_VERTEX_SHADER_SRC = """
#version 450
layout (location = 0) in vec2 position;
layout (location = 1) in vec4 color;

out vec4 frag_color;

uniform vec2 manual_offset;

uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  position;
	vec2  GAME_DIMENSIONS;
	vec2  dimensions;
} camera;

void main() {
	frag_color = color;

	gl_Position =
		window.projection *
		window.view *
		vec4(position + manual_offset, 0.0, 1.0);
}
"""

TIMING_GRAPH_QUAD_FRAGMENT_SHADER_SRC = """
#version 450

in vec4 frag_color;

out vec4 final_color;

void main() {
	final_color = frag_color;
}
"""

_TIMING_GRAPH_QUAD_SHADER_CONTAINER = ShaderContainer(
	TIMING_GRAPH_QUAD_VERTEX_SHADER_SRC,
	TIMING_GRAPH_QUAD_FRAGMENT_SHADER_SRC,
)


class TimingGraph:
	def __init__(
		self,
		x: float,
		y: float,
		height: float,
		danger_zone_start: float,
		sample_count: int,
		colors: t.Sequence["ctypes.Array"],
		idxbuf_id,
	) -> None:
		self._shader = _TIMING_GRAPH_QUAD_SHADER_CONTAINER.get_program()

		self._x = x
		self._y = y
		self._danger_zone_start = danger_zone_start
		self._height = height
		self._sample_to_height_factor = (danger_zone_start / height)

		self._samples = [0.0] * sample_count
		self.sample_count = sample_count
		self._sample_cursor = 0

		self._colors = colors
		self._color_idx = 0

		self._coord_vbo = RAMBackedBufferObject(
			gl.GL_ARRAY_BUFFER, 0, gl.GL_DYNAMIC_DRAW, gl.GL_DOUBLE, 2
		)
		self._coord_vbo.set_size_and_data_py([
			x
			for i in range(sample_count)
			for x in (i + 0.0, 0.0, i + 0.0, 0.0, i + 1.0, 0.0, i + 1.0, 0.0)
		])

		self._color_vbo = RAMBackedBufferObject(
			gl.GL_ARRAY_BUFFER,
			GL_TYPE_SIZES[gl.GL_UNSIGNED_BYTE] * 4 * 4 * sample_count,
			gl.GL_DYNAMIC_DRAW,
			gl.GL_UNSIGNED_BYTE,
			4,
		)
		gl.glClearNamedBufferData(
			self._color_vbo.id, gl.GL_RGBA8, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, colors[0]
		)

		self._vao = gl.GLuint()
		gl.glCreateVertexArrays(1, ctypes.byref(self._vao))
		gl.glEnableVertexArrayAttrib(self._vao, 0)
		gl.glEnableVertexArrayAttrib(self._vao, 1)
		gl.glVertexArrayAttribFormat(self._vao, 0, 2, gl.GL_DOUBLE, gl.GL_FALSE, 0)
		gl.glVertexArrayAttribFormat(self._vao, 1, 4, gl.GL_UNSIGNED_BYTE, gl.GL_TRUE, 0)
		gl.glVertexArrayVertexBuffer(
			self._vao, 0, self._coord_vbo.id, 0, GL_TYPE_SIZES[gl.GL_DOUBLE] * 2
		)
		gl.glVertexArrayVertexBuffer(
			self._vao, 1, self._color_vbo.id, 0, GL_TYPE_SIZES[gl.GL_UNSIGNED_BYTE] * 4
		)
		gl.glVertexArrayAttribBinding(self._vao, 0, 0)
		gl.glVertexArrayAttribBinding(self._vao, 1, 1)
		gl.glVertexArrayElementBuffer(self._vao, idxbuf_id)

	def push(self, value: float) -> None:
		self._samples[self._sample_cursor] = value
		vis_y = value * self._sample_to_height_factor
		color_array = self._colors[self._color_idx]
		if vis_y > self._height:
			# Crappily blend with red, anything >1s becomes full red, yeah
			# this is hardcoded as hell
			ratio = clamp(value / 1000.0, 0.5, 1.0)
			vis_y = self._height
			color_array = (ctypes.c_ubyte * 16)(
				*(
					(
						int(color_array[0] + (color_array[0] - 0xFF) * ratio),
						int(color_array[1] - color_array[1] * ratio),
						int(color_array[2] - color_array[2] * ratio),
						color_array[3],
				) * 4)
			)

		self._coord_vbo.set_data_array(
			(self._sample_cursor * 8 + 1) * GL_TYPE_SIZES[gl.GL_DOUBLE],
			GL_TYPE_SIZES[gl.GL_DOUBLE],
			(ctypes.c_double * 1)(-vis_y),
		)
		self._coord_vbo.set_data_array(
			(self._sample_cursor * 8 + 7) * GL_TYPE_SIZES[gl.GL_DOUBLE],
			GL_TYPE_SIZES[gl.GL_DOUBLE],
			(ctypes.c_double * 1)(-vis_y),
		)
		self._color_vbo.set_data_array(
			(self._sample_cursor * 16) * GL_TYPE_SIZES[gl.GL_UNSIGNED_BYTE],
			GL_TYPE_SIZES[gl.GL_UNSIGNED_BYTE] * 16,
			color_array,
		)

		self._sample_cursor += 1
		if self._sample_cursor >= self.sample_count:
			self._sample_cursor = 0

	def advance_color(self):
		self._color_idx = (self._color_idx + 1) % len(self._colors)

	def draw(self):
		# Draw the super fancy debug lines here with the most convoluted logic imaginable
		self._shader.use()

		sample_idx = self._sample_cursor
		sample_count = self.sample_count

		self._coord_vbo.ensure()
		self._color_vbo.ensure()

		gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glBindVertexArray(self._vao)

		self._shader["manual_offset"] = (self._x - sample_idx, self._y)
		gl.glDrawElements(
			gl.GL_TRIANGLES,
			(sample_count - sample_idx) * 6,
			gl.GL_UNSIGNED_SHORT,
			ctypes.c_void_p(sample_idx * 6 * GL_TYPE_SIZES[gl.GL_UNSIGNED_SHORT]),
		)

		if sample_idx != 0:
			self._shader["manual_offset"] = (self._x - sample_idx + sample_count, self._y)
			gl.glDrawElements(gl.GL_TRIANGLES, (sample_idx - 1) * 6, gl.GL_UNSIGNED_SHORT, None)

		gl.glBindVertexArray(0)


class DebugPane(SuperScene):
	"""
	Shoddy class to manage text lines and update times on rectangles,
	used to display debug messages, timing information and cache stats.
	"""

	FONT_SIZE = 8
	FPS_FONT_SIZE = 10
	LINE_DIST = 2
	PADDING = 8

	def __init__(
		self,
		line_amount: int,
		message_queue: queue.Queue,
		update_times_graph_size: int,
		draw_times_graph_size: int,
	) -> None:
		super().__init__(CNST.GAME_WIDTH, CNST.GAME_HEIGHT)

		self.insert_index = 0
		self._line_amount = line_amount
		self._queue = message_queue

		self.background = PNFGroup(order=0)
		self.foreground = PNFGroup(order=1)
		self.batch = PNFBatch()

		self.debug_rect = PNFSprite(
			x = self.PADDING,
			y = 0,
			context = self.get_context(self.background),
		)
		self.debug_rect.make_rect(
			to_rgba_tuple(0x2020AA7F),
			CNST.GAME_WIDTH - 2 * self.PADDING,
			(self.FONT_SIZE * (line_amount + 1)) + (self.LINE_DIST * (line_amount - 1)),
		)

		# HACK getting the ascent like this
		bluegh = font.load("Consolas", self.FPS_FONT_SIZE).ascent
		self.timing_rect = PNFSprite(
			x = self.PADDING,
			y = self.debug_rect.y + self.debug_rect.height + self.PADDING,
			context = self.get_context(self.background),
		)
		self.timing_rect.make_rect(
			to_rgba_tuple(0x3F3F3FB7), CNST.GAME_WIDTH // 3, (bluegh * 2) + 6,
		)

		self.memory_rect = PNFSprite(
			x = self.PADDING,
			y = self.timing_rect.y + self.timing_rect.height + self.PADDING,
			context = self.get_context(self.background),
		)
		self.memory_rect.make_rect(
			to_rgba_tuple(0x747474B7), CNST.GAME_WIDTH // 3, (bluegh * 3) + 6
		)

		self.debug_labels = [
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
			y = int(self.timing_rect.y),
			font_name = "Consolas",
			font_size = self.FPS_FONT_SIZE,
			multiline = True,
			context = self.get_context(self.foreground),
		)

		self.memory_label = PNFText(
			x = 10,
			y = int(self.memory_rect.y),
			font_name = "Consolas",
			font_size = self.FPS_FONT_SIZE,
			multiline = True,
			context = self.get_context(self.foreground),
		)

		timing_graph_colors = (
			(ctypes.c_ubyte * (4 * 4))(*((123, 182, 232, 255) * 4)),
			(ctypes.c_ubyte * (4 * 4))(*((211, 242, 255, 255) * 4)),
		)

		# Standard quad index buffer shared among the graphs: Why use two if one do trick?
		# That saved kilobyte is gonna pay for itself in no time
		largest_graph_size = max(update_times_graph_size, draw_times_graph_size)
		self._timing_graph_index_buffer = BufferObject(
			gl.GL_ELEMENT_ARRAY_BUFFER,
			GL_TYPE_SIZES[gl.GL_UNSIGNED_SHORT] * 6 * largest_graph_size,
			gl.GL_STATIC_READ,
			gl.GL_UNSIGNED_SHORT,
			1,
		)
		self._timing_graph_index_buffer.set_data_py(
			0,
			largest_graph_size * 6,
			[
				x
				for i in range(0, largest_graph_size * 4, 4)
				for x in (0+i, 1+i, 2+i, 0+i, 2+i, 3+i)
			],
		)

		self._update_timing_graph = TimingGraph(
			288.0,
			self.timing_rect.y + bluegh,
			12.0,
			20.0,
			update_times_graph_size,
			timing_graph_colors,
			self._timing_graph_index_buffer.id,
		)
		self._draw_timing_graph = TimingGraph(
			288.0,
			self.timing_rect.y + bluegh * 2,
			12.0,
			20.0,
			draw_times_graph_size,
			timing_graph_colors,
			self._timing_graph_index_buffer.id,
		)

	def bump_draw_graph(self, draw_time: float) -> None:
		self._draw_timing_graph.push(draw_time)

	def bump_update_graph(self, update_time: float) -> None:
		self._update_timing_graph.push(update_time)

	def update_averages(
		self, ups: int, dps: int, update_avg: str, update_max: str, draw_avg: str, draw_max: str,
	) -> None:
		self._update_timing_graph.advance_color()
		self._draw_timing_graph.advance_color()
		self.timing_label.text = (
			f"UPDATE: {ups:>3}/s, avg {update_avg}, max {update_max}\n"
			f"DRAW:   {dps:>3}/s, avg {draw_avg}, max {draw_max}\n"
		)

	def update(self) -> None:
		"""
		Updates the debug pane and writes all queued messages to
		the labels, causing a possibly overflowing label's text to be
		deleted and bumping up all other labels.
		Call this when OpenGL allows it.
		"""
		if self._queue.empty():
			return

		while True:
			try:
				message = self._queue.get_nowait()
			except queue.Empty:
				break

			if self.insert_index == len(self.debug_labels):
				self.insert_index -= 1
				for i in range(len(self.debug_labels) - 1):
					self.debug_labels[i].text = self.debug_labels[i + 1].text

			self.debug_labels[self.insert_index].text = message
			self.insert_index += 1

	def draw(self) -> None:
		super().draw()
		self._update_timing_graph.draw()
		self._draw_timing_graph.draw()
