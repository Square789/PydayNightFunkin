
import math

from pyglet.shapes import Rectangle


class TLRectangle(Rectangle):
	def _update_position(self):
		if not self._visible:
			self._vertex_list.position[:] = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
		elif self._rotation:
			# TODO rotate maybe?
			x1 = -self._anchor_x
			y1 = -self._anchor_y
			x2 = x1 + self._width
			y2 = y1 - self._height
			x = self._x
			y = self._y

			r = -math.radians(self._rotation)
			cr = math.cos(r)
			sr = math.sin(r)
			ax = x1 * cr - y1 * sr + x
			ay = x1 * sr + y1 * cr + y
			bx = x2 * cr - y1 * sr + x
			by = x2 * sr + y1 * cr + y
			cx = x2 * cr - y2 * sr + x
			cy = x2 * sr + y2 * cr + y
			dx = x1 * cr - y2 * sr + x
			dy = x1 * sr + y2 * cr + y
			self._vertex_list.position[:] = (ax, ay, bx, by, cx, cy, ax, ay, cx, cy, dx, dy)
		else:
			x1 = self._x - self._anchor_x
			y1 = self._y - self._anchor_y
			x2 = x1 + self._width
			y2 = y1 + self._height

			y1, y2 = y2, y1

			self._vertex_list.position[:] = (x1, y1, x2, y1, x2, y2, x1, y1, x2, y2, x1, y2)
