
from math import pi, sin
import typing as t

from pyday_night_funkin.core.utils import clamp


T = t.TypeVar("T")

class HasVisible(t.Protocol):
	visible: bool

HasVisibleT = t.TypeVar("HasVisibleT", bound=HasVisible)
HashableT = t.TypeVar("HashableT", bound=t.Hashable)


class BaseEffect(t.Generic[T]):
	"""
	Abstract class representing an effect running for some time.
	"""

	def __init__(
		self,
		duration: float,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		if duration <= 0.0:
			raise ValueError("Duration may not be negative or zero!")

		self.on_complete = on_complete
		self.duration = duration
		self.cur_time = 0.0

	def update(self, dt: float, obj: T) -> None:
		raise NotImplementedError("Subclass this")

	def is_finished(self) -> bool:
		return self.cur_time >= self.duration


class Tween(BaseEffect[T]):
	def __init__(
		self,
		tween_func: t.Callable[[float], float],
		attr_map: t.Dict[str, t.Tuple[t.Any, t.Any]],
		duration: float,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		super().__init__(duration, on_complete)
		self.tween_func = tween_func
		self.attr_map = attr_map

	def update(self, dt: float, obj: T) -> None:
		self.cur_time += dt
		progress = self.tween_func(clamp(self.cur_time, 0.0, self.duration) / self.duration)

		for attr_name, (v_ini, v_diff) in self.attr_map.items():
			setattr(obj, attr_name, v_ini + v_diff*progress)


# NOTE: Left here since i would need to replace call sites with some
# ugly lambda s: setattr(s, "visibility", True) stuff; not really
# worth it, see into it if you have time.
class Flicker(BaseEffect[HasVisibleT]):
	"""
	Effect rapidly turning a sprite's visibility off and on.
	This is a special case of the more generic `Toggle` effect
	affecting only a sprite's visibility.
	"""
	def __init__(
		self,
		interval: float,
		start_visibility: bool,
		end_visibility: bool,
		duration: float,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		super().__init__(duration, on_complete)
		if interval <= 0.0:
			raise ValueError("Interval may not be negative or zero!")

		self.interval = interval
		self.end_visibility = end_visibility
		self._next_toggle = interval
		self._visible = start_visibility

	def update(self, dt: float, obj: HasVisibleT) -> None:
		self.cur_time += dt
		if self.is_finished():
			obj.visible = self.end_visibility
			return

		if self.cur_time >= self._next_toggle:
			while self.cur_time >= self._next_toggle:
				self._next_toggle += self.interval
			self._visible = not self._visible
			obj.visible = self._visible


class Toggle(BaseEffect[T]):
	"""
	Periodically calls on/off callbacks on a sprite for a given
	duration.
	"""
	def __init__(
		self,
		interval: float,
		start_active: bool,
		end_active: bool,
		duration: float,
		on_toggle_on: t.Optional[t.Callable[[T], t.Any]] = None,
		on_toggle_off: t.Optional[t.Callable[[T], t.Any]] = None,
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		super().__init__(duration, on_complete)
		if interval <= 0.0:
			raise ValueError("Interval may not be negative or zero!")

		self._cur_state = start_active
		self._invert = -1 if not start_active else 1
		self.interval = pi/interval
		self.end_active = end_active
		self.on_toggle_on = on_toggle_on
		self.on_toggle_off = on_toggle_off

	def update(self, dt: float, obj: T) -> None:
		self.cur_time += dt
		new_state = (sin(self.cur_time * self.interval) * self._invert) > 0
		if self._cur_state == new_state:
			return

		self._cur_state = new_state
		if new_state:
			if self.on_toggle_on is not None:
				self.on_toggle_on(obj)
		else:
			if self.on_toggle_off is not None:
				self.on_toggle_off(obj)
