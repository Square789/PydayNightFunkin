
import typing as t

from pyday_night_funkin.core.scene import BaseScene, SceneKernel


class SceneManager:
	def __init__(self) -> None:
		self._scene_stack: t.List[BaseScene] = []
		self._scenes_to_draw: t.List[BaseScene] = []
		self._scenes_to_update: t.List[BaseScene] = []
		self._pending_scene_stack_removals: t.Set[BaseScene] = set()
		self._pending_scene_stack_additions: t.List[SceneKernel] = []

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
				kernel = self._pending_scene_stack_additions.pop(0)
				self._scene_stack.append(kernel.create_scene(self))
			self._on_scene_stack_change()

	def _maybe_get_kernel(
		self, scene_type_or_kernel: t.Union[t.Type[BaseScene], SceneKernel]
	) -> SceneKernel:
		if isinstance(scene_type_or_kernel, type) and issubclass(scene_type_or_kernel, BaseScene):
			return scene_type_or_kernel.get_kernel()
		else:
			return scene_type_or_kernel

	def push_scene(self, type_or_kernel: t.Union[t.Type[BaseScene], SceneKernel]) -> None:
		"""
		Requests push of a new scene kernel onto the scene stack which
		will then become the topmost scene.
		Note that this method will not do its job if a scene has
		already been pushed before in this update tick. Use
		`push_scene_always` for that.
		"""
		if not self._pending_scene_stack_additions:
			self.push_scene_always(type_or_kernel)

	def push_scene_always(self, type_or_kernel: t.Union[t.Type[BaseScene], SceneKernel]) -> None:
		"""
		Requests push of a new scene kernel onto the scene stack, which
		will then become the topmost scene.
		"""
		self._pending_scene_stack_additions.append(self._maybe_get_kernel(type_or_kernel))

	def set_scene(self, type_or_kernel: t.Union[t.Type[BaseScene], SceneKernel]) -> bool:
		"""
		Arranges for clearing of the existing scene stack and addition
		of the given scene kernel passed in the same manner as in
		`push_scene` to be its only member. Clears any possibly
		pending scene additions beforehand as well.
		The first scene's `on_imminent_replacement` method will be
		called with the new kernel as an argument, where it may deny
		the switch altogether.
		Returns whether the first scene denied the set.
		"""
		kernel = self._maybe_get_kernel(type_or_kernel)
		if self._scene_stack and not self._scene_stack[0].on_imminent_replacement(kernel):
			return False

		for scene in self._scene_stack:
			self._pending_scene_stack_removals.add(scene)
		self._pending_scene_stack_additions.clear()

		# self.push_scene_always(kernel)
		self._pending_scene_stack_additions.append(kernel)

		return True

	def remove_scene(self, scene: BaseScene) -> None:
		"""
		Requests removal of the given scene from anywhere in the
		scene stack.
		"""
		self._pending_scene_stack_removals.add(scene)

	def get_previous_scene(self, scene: BaseScene) -> t.Optional[BaseScene]:
		"""
		Returns the scene previous to `scene` in the scene stack, or
		`None` if it's the first one.
		"""
		i = self._scene_stack.index(scene)
		return self._scene_stack[i - 1] if i > 0 else None

	def get_next_scene(self, scene: BaseScene) -> t.Optional[BaseScene]:
		"""
		Returns the scene after `scene` in the scene stack, or `None`
		if it's the last one.
		"""
		i = self._scene_stack.index(scene)
		return self._scene_stack[i + 1] if i < len(self._scene_stack) - 1 else None
