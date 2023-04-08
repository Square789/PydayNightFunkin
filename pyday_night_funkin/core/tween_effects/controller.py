
from math import pi, sin
import typing as t

from .eases import linear
from .effects import BaseEffect, Flicker, Toggle, Tween

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.scene_object import WorldObject


T = t.TypeVar("T")

class HasVisible(t.Protocol):
	visible: bool

HasVisibleT = t.TypeVar("HasVisibleT", bound=HasVisible)
HashableT = t.TypeVar("HashableT", bound=t.Hashable)


class EffectController:
	def __init__(self) -> None:
		self._tweens: t.Dict[t.Hashable, t.Set["BaseEffect"]] = {}
		"""All of this controller's tweens."""

	def _add(self, obj: t.Hashable, tw: "BaseEffect") -> None:
		if obj not in self._tweens:
			self._tweens[obj] = set()
		self._tweens[obj].add(tw)

	def tween(
		self,
		obj: HashableT,
		attributes: t.Dict[str, t.Any],
		duration: float,
		ease: t.Callable[[float], float] = linear,
		on_complete: t.Optional[t.Callable[[HashableT], t.Any]] = None,
	) -> None:
		# 0: initial value; 1: difference
		attr_map = {}
		for attribute_name, target_value in attributes.items():
			initial_value = getattr(obj, attribute_name)
			attr_map[attribute_name] = (initial_value, target_value - initial_value)

		tw = Tween(ease, attr_map, duration, on_complete)
		self._add(obj, tw)

	def flicker(
		self,
		obj: HasVisibleT,
		duration: float,
		interval: float,
		end_visibility: bool = True,
		on_complete: t.Optional[t.Callable[[HasVisibleT], t.Any]] = None,
	) -> None:
		f = Flicker(interval, obj.visible, end_visibility, duration, on_complete)
		self._add(obj, f)

	def toggle(
		self,
		obj: HashableT,
		duration: float,
		interval: float,
		start_status: bool = True,
		end_status: bool = True,
		on_toggle_on: t.Optional[t.Callable[[HashableT], t.Any]] = None,
		on_toggle_off: t.Optional[t.Callable[[HashableT], t.Any]] = None,
		on_complete: t.Optional[t.Callable[[HashableT], t.Any]] = None,
	) -> None:
		tgl = Toggle(
			interval, start_status, end_status, duration, on_toggle_on, on_toggle_off, on_complete
		)
		self._add(obj, tgl)

	def remove_of(self, obj: t.Hashable = None) -> None:
		"""
		Removes effects of the given object from the tween controller.
		Supply nothing to clear all effects. This will abruptly stop
		all effects without calling their on_complete callbacks.
		"""
		if obj is None:
			self._tweens.clear()
		else:
			self._tweens.pop(obj, None)

	def update(self, dt: float) -> None:
		if not self._tweens:
			return

		finished: t.List[t.Tuple[t.Hashable, BaseEffect]] = []
		for o, tween_set in self._tweens.items():
			for tween in tween_set:
				tween.update(dt, o)
				if tween.is_finished():
					finished.append((o, tween))

		for o, tween in finished:
			if tween.on_complete is not None:
				tween.on_complete(o)
			self._tweens[o].remove(tween)
			if len(self._tweens[o]) == 0:
				self._tweens.pop(o)

	def destroy(self):
		del self._tweens
