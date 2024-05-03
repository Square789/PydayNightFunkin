
import typing as t

from loguru import logger

from pyday_night_funkin.core.camera import Camera
from pyday_night_funkin.core.graphics import PNFGroup
from pyday_night_funkin.core.pnf_sprite import PNFSprite
from pyday_night_funkin.core.scene_context import CamSceneContext, SceneContext
from pyday_night_funkin.core.scene_object import SceneObject


SceneObjectT = t.TypeVar("SceneObjectT", bound=SceneObject)


class Container(SceneObject[SceneContext] if t.TYPE_CHECKING else SceneObject):
	"""
	A glorified list wrapper that contains multiple SceneObjects
	and can apply operations to them.
	A container should never have any sort of graphical
	representation, it only serves as a building block of the scene
	hierarchy.
	"""

	def __init__(self, context: t.Optional[SceneContext] = None, ordered: bool = False) -> None:
		super().__init__(SceneContext.create_empty() if context is None else context)

		self._ordered = ordered
		self._next_order = 0
		self._members: t.List[SceneObject] = []
		# self._member_to_layer_map: t.Dict[SceneObject, t.Optional["SceneLayer"]] = {}
		self._layers: t.List["SceneLayer"] = []

	def set_context(self, new_context: SceneContext) -> None:
		self._context = new_context

		if self._layers:
			logger.warning(
				"Context of an OrderedContainer with layers modified. Expect graphical problems."
			)

		if self._ordered:
			layer_count = len(self._layers)
			for i, lyr in enumerate(self._layers):
				lyr.set_context(self._context.inherit(i))
			# for i, (m, lyr) in enumerate(self._member_to_layer_map.items()):
			for i, m in enumerate(self._members):
				m.set_context(self._context.inherit(i + layer_count))
		else:
			for i, lyr in enumerate(self._layers):
				lyr.set_context(self._context.inherit())
			# for i, (m, lyr) in enumerate(self._member_to_layer_map.items()):
			for m in self._members:
				m.set_context(self._context.inherit())

	def set_cam_context(self, new_cam_context: CamSceneContext) -> None:
		"""
		Sets this ``Container``'s context to a ``CamSceneContext``.

		Since containers do not care about cameras, this calls directly into
		``set_context``.
		"""
		self.set_context(new_cam_context)

	def create_layer(
		self,
		ordered: bool = False,
		parent_layer: t.Optional["SceneLayer"] = None,
		before: t.Optional["SceneLayer"] = None,
		after: t.Optional["SceneLayer"] = None,
	) -> "SceneLayer":
		"""
		Creates a ``SceneLayer``.

		Scene layers are very finnicky and quite honestly pointless objects
		that i am this short from removing due to the way they absolutely
		drag dirt across what could be otherwise pretty straightforward
		container logic.
		Seriously, i wrote all this to see if it would work, and it does,
		but it's just awful rn (0.0.56).

		Layers are containers that help in controlling a draw tree while
		not actually being standard containers that, well, contain your
		objects.

		Unlike a cascade of containers, all drawables added to a container's
		layers stay directly in the ``_members`` of it.

		Layers do not have any management power over items drawn through
		them and are useful purely for managing the ordering of your
		container's drawables.

		Layers may be inserted in front or after another layer via the
		``before``/``after`` parameters, but this will break when any non-
		layer members exist in the container.
		Furthermore, layers break horribly when a container with layers
		changes context or when it is sorted.

		They can be created with forced order, where they will cause all
		drawables added to them in the order they were added.

		Cameras are irrelevant to ``SceneLayer``s, as they are always filled
		in seperately on drawable creation.
		"""
		if before is not None and after is not None:
			raise ValueError("Only specify at most one of 'before', 'after'")

		if not self._ordered and not ordered:
			logger.info(
				"Adding unordered layers to unordered layers introduces more complexity "
				"than needed to the draw tree."
			)

		is_insertion = before is not None or after is not None
		if is_insertion:
			if parent_layer is None:
				lyr = self._insert_layer(ordered, before, after)
			else:
				lyr = parent_layer._insert_layer(ordered, before, after)

		else:
			lyr = SceneLayer(self.get_context(parent_layer, ()), ordered)
			if parent_layer is None:
				self._layers.append(lyr)
			else:
				parent_layer._layers.append(lyr)

		return lyr

	def _insert_layer(
		self, ordered: bool, before: t.Optional["SceneLayer"], after: t.Optional["SceneLayer"]
	) -> "SceneLayer":
		if self._members:
			logger.warning(
				"Inserting layers when non-layer members exist will ruin their ordering."
			)

		if before is not None:
			new_layer_idx = self._layers.index(before)
		else:  # after is not None
			new_layer_idx = self._layers.index(after) + 1

		# someone couldve technically added and removed stuff to push up
		# the layers, just reparent all of them
		to = self._next_order
		self._next_order = 0
		for i in range(new_layer_idx):
			self._layers[i].set_context_group(self._get_context_group())
		for i in range(new_layer_idx, len(self._layers)):
			g = self._get_context_group()
			g.order += 1
			self._layers[i].set_context_group(g)

		ctx = self.get_context(None, ())
		ctx.group.order = new_layer_idx
		self._next_order = to + 1

		lyr = SceneLayer(ctx, ordered)
		self._layers.insert(new_layer_idx, lyr)
		return lyr

	def _get_order(self) -> int:
		if self._ordered:
			order = self._next_order
			self._next_order += 1
			return order
		else:
			return 0

	def _get_context_group(self) -> PNFGroup:
		"""
		Returns a new group that can be given to a drawable to attach
		it to this container.

		Increments the attachment order of this container if it's ordered.
		"""
		return PNFGroup(self._context.group, self._get_order())

	def get_context(
		self,
		layer: t.Optional["SceneLayer"] = None,
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]] = None,
	) -> CamSceneContext:
		"""
		Creates a ``CamSceneContext`` for a ``SceneObject`` to use.

		The given ``layer`` and ``cameras`` are turned into an appropiate
		``SceneContext`` that can be passed onto a child of this container.

		If no layer is supplied, will add the object under this container's
		draw tree root directly.

		If no cameras are supplied, will not draw the object on any cameras,
		making this relatively pointless.
		"""
		if cameras is None:
			actual_cameras = ()
		elif isinstance(cameras, Camera):
			actual_cameras = (cameras,)
		else:
			actual_cameras = cameras

		if layer is None:
			return CamSceneContext(self._context.batch, self._get_context_group(), actual_cameras)
		else:
			return layer.get_context(None, actual_cameras)

	def add(
		self,
		object: SceneObject,
		layer: t.Optional["SceneLayer"] = None,
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]] = None,
	) -> None:
		"""
		Adds a ``SceneObject`` to this container on the given layer, drawing
		itself on the given cameras.

		Note that this may become ugly if the object is owned by
		another scene, be sure to remove it from there with
		``remove(keep=True)`` beforehand.

		See ``get_context`` to find out how ``layer`` and ``cameras`` are
		actually used.
		"""
		self._members.append(object)
		# self._member_to_layer_map[object] = layer
		object.set_cam_context(self.get_context(layer, cameras))

	# object_class is given as a kwarg somewhere.
	# layer and cameras may also appear either as arg or kwarg.
	@t.overload
	def create_object(
		self,
		layer: t.Optional["SceneLayer"] = None,
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]] = None,
		*,
		object_class: t.Type[SceneObjectT],
		**kwargs,
	) -> SceneObjectT:
		...

	# Everything is listed positionally, object_class is arg 3
	@t.overload
	def create_object(
		self,
		layer: t.Optional["SceneLayer"],
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]],
		object_class: t.Type[SceneObjectT],
		/,
		*args,
		**kwargs,
	) -> SceneObjectT:
		...

	# object_class is not given, return type is PNFSprite.
	@t.overload
	def create_object(
		self,
		layer: t.Optional["SceneLayer"] = None,
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]] = None,
		/,
		**kwargs,
	) -> PNFSprite:
		...

	def create_object(
		self,
		layer: t.Optional["SceneLayer"] = None,
		cameras: t.Optional[t.Union[Camera, t.Iterable[Camera]]] = None,
		object_class: t.Type[SceneObjectT] = PNFSprite,
		*args,
		**kwargs,
	) -> t.Union[SceneObjectT, PNFSprite]:
		"""
		Creates a scene object on the given layer belonging to one or
		multiple cameras. If one or more camera names are specified, the
		object will be registered with them.

		The object will be created from the given ``object_class`` type
		with all args and kwargs. Note that because they are so fundamental,
		by default the object class is `PNFSprite`.

		The object will be given a fitting ``context`` filled in by the
		scene if not otherwise given. (And if you give it a custom one, you
		better know what you're doing.)

		Note that ``self.create_object(lyr, cam, Cls, 1, 2, n=3)`` is
		effectively equivalent to
		``x = Cls(1, 2, n=3); self.add(x, lyr, cam)``, but a bit faster as
		no migration from a virtual batch to the scene's batch has to happen.
		"""
		if "context" not in kwargs:
			kwargs["context"] = self.get_context(layer, cameras)

		obj = object_class(*args, **kwargs)
		self._members.append(obj)
		# self._member_to_layer_map[obj] = layer
		if layer is not None:
			layer._members.append(obj)

		return obj

	def remove(self, object: SceneObject, keep: bool = False) -> None:
		"""
		Removes something from this container.

		If ``keep`` is set to ``True``, will not delete the removed object.

		If the object is unknown to the container, does nothing.
		"""
		if object in self._members:
			self._members.remove(object)
			# self._member_to_layer_map.pop(object)._members.remove(object)
			if keep:
				object.invalidate_context()
			else:
				object.delete()

	def sort(self, compfn: t.Optional[t.Callable] = None) -> None:
		"""
		Sorts the container's members by the given comparison function.

		This method will break graphical ordering for any members added to
		layers of this containers.

		The function must be able to handle any ``SceneObject`` added to
		this container and, for each one, return a stand-in value that will
		be used to sort it.
		"""
		if self._layers:
			logger.warning(
				"Ordering a container with layers will ruin layer-dictated order."
			)

		# NOTE: could set next order here to reduce it but eh
		self._members.sort(key=compfn)
		for i, m in enumerate(self._members):
			m.set_context_group(PNFGroup(self._context.group, i if self._ordered else 0))

	def delete(self) -> None:
		for m in self._members:
			m.delete()
		self._members.clear()

		for lyr in self._layers:
			lyr.delete()
		self._layers.clear()

		del self._context

	def update(self, dt: float) -> None:
		for m in self._members.copy():
			m.update(dt)


class SceneLayer(Container):
	"""
	Layers are an awkward drawable ordering mechanism for containers.

	More is explained in ``SceneObject.create_layer``.
	"""

	def add(self, *_, **__) -> None:
		raise RuntimeError("Cannot add to layers")

	def remove(self, *_, **__) -> None:
		raise RuntimeError("Cannot remove from layers")

	def sort(self, _) -> None:
		raise RuntimeError("Cannot sort layers")

	def get_context(
		self,
		layer: t.Optional["SceneContext"] = None,
		cameras: t.Optional[t.Union["Camera", t.Iterable["Camera"]]] = None,
	) -> CamSceneContext:
		if layer is not None:
			raise RuntimeError("Do not request contexts parented to layers from layers")

		return super().get_context(None, cameras)

	def create_layer(self) -> "SceneLayer":
		raise RuntimeError(
			"Scene layers need to be created through the actual container that should own them"
		)

	def delete(self) -> None:
		# assume that a layer's members are already deleted by the container actually owning them.
		# no point in using invalidate_context or something like that
		self._members.clear()

		for lyr in self._layers:
			lyr.delete()
		self._layers.clear()

		del self._context

	def update(self, dt: float) -> None:
		return
