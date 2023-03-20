
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.scene import BaseScene

SceneSetupTrio = t.Tuple[t.Type["BaseScene"], t.Tuple[t.Any], t.Dict[str, t.Any]]


class SceneManager:
	def __init__(self) -> None:
		self._scene_stack: t.List["BaseScene"] = []
		self._scenes_to_draw: t.List["BaseScene"] = []
		self._scenes_to_update: t.List["BaseScene"] = []
		self._pending_scene_stack_removals: t.Set["BaseScene"] = set()
		self._pending_scene_stack_additions: t.List[SceneSetupTrio] = []

	def _on_scene_stack_change(self) -> None:
		i = len(self._scene_stack) - 1
		while i > 0 and self._scene_stack[i].draw_passthrough:
			i -= 1
		self._scenes_to_draw = self._scene_stack[i:]

		i = len(self._scene_stack) - 1
		while i > 0 and self._scene_stack[i].update_passthrough:
			i -= 1
		self._scenes_to_update = self._scene_stack[i:]

	def _modify_scene_stack(self) -> float:
		"""Applies outstanding modifications to the scene stack."""
		# This stuff can't be done exactly when a scene demands it since
		# then we would be looking at a mess of half-dead scenes still
		# running their update code and erroring out.
		if self._pending_scene_stack_removals:
			for i, scene in enumerate(self._scene_stack[::-1]): # reverse shallow copy
				if scene not in self._pending_scene_stack_removals:
					continue
				self._scene_stack.remove(scene)
				scene.destroy()
			self._on_scene_stack_change()
			self._pending_scene_stack_removals.clear()

		if self._pending_scene_stack_additions:
			# Iterate like this as scenes may push more scenes in their __init__
			while self._pending_scene_stack_additions:
				scene_type, args, kwargs = self._pending_scene_stack_additions.pop(0)
				new_scene = scene_type(self, *args, **kwargs)
				self._scene_stack.append(new_scene)
			self._on_scene_stack_change()

	def push_scene(self, new_scene_cls: t.Type["BaseScene"], *args, **kwargs) -> None:
		"""
		Requests push of a new scene onto the scene stack which will
		then be the topmost scene.
		The game instance will be passed as the first argument to the
		scene class, with any args and kwargs following it.
		Note that this method will not do its job if a scene has
		already been pushed before in this update tick. Use
		`push_scene_always` for that.
		"""
		if not self._pending_scene_stack_additions:
			self._pending_scene_stack_additions.append((new_scene_cls, args, kwargs))

	def push_scene_always(self, new_scene_cls: t.Type["BaseScene"], *args, **kwargs) -> None:
		"""
		Requests push of a new scene onto the scene stack, which will
		then be the topmost scene.
		The game instance will be passed as the first argument to the
		scene class, with any args and kwargs following it.
		"""
		self._pending_scene_stack_additions.append((new_scene_cls, args, kwargs))

	def set_scene(self, new_scene_type: t.Type["BaseScene"], *args, **kwargs) -> bool:
		"""
		Arranges for clearing of the existing scene stack and addition
		of the given scene passed in the same manner as in `push_scene`
		to be its only member. Clears any possibly pending scene
		additions beforehand as well.
		The first scene's `on_imminent_replacement` method will be
		called where it may deny the switch altogether.
		Returns whether the first scene denied the set.
		"""
		if (
			self._scene_stack and
			not self._scene_stack[0].on_imminent_replacement(new_scene_type, *args, **kwargs)
		):
			return False

		for scene in self._scene_stack:
			self._pending_scene_stack_removals.add(scene)
		self._pending_scene_stack_additions.clear()

		self.push_scene(new_scene_type, *args, **kwargs)

		return True

	def remove_scene(self, scene: "BaseScene") -> None:
		"""
		Requests removal of the given scene from anywhere in the
		scene stack.
		"""
		self._pending_scene_stack_removals.add(scene)

	def get_previous_scene(self, scene: "BaseScene") -> t.Optional["BaseScene"]:
		"""
		Returns the scene previous to `scene` in the scene stack, or
		`None` if it's the first one.
		"""
		i = self._scene_stack.index(scene)
		return self._scene_stack[i - 1] if i > 0 else None

	def get_next_scene(self, scene: "BaseScene") -> t.Optional["BaseScene"]:
		"""
		Returns the scene after `scene` in the scene stack, or `None`
		if it's the last one.
		"""
		i = self._scene_stack.index(scene)
		return self._scene_stack[i + 1] if i < len(self._scene_stack) - 1 else None
