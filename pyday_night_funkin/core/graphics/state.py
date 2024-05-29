from __future__ import annotations

from functools import partial
import typing as t

from pyglet.gl import gl
from pyglet.graphics import shader

if t.TYPE_CHECKING:
	import ctypes
	from pyglet.image import Texture
	from pyglet.graphics.shader import ShaderProgram, UniformBufferObject


class StatePart:
	# `cost` and `required` are ignored for now and probably for a long future
	cost: int = -1
	gl_func: t.Callable | None = None
	required: t.Sequence[t.Type[StatePart] | t.Tuple[t.Type[StatePart], t.Tuple]] = ()
	only_one: bool = True

	def __init__(self) -> None:
		self.args = ()

	def concretize(self, *_) -> t.Tuple[t.Tuple, t.Callable[[], t.Any]]:
		"""
		This method is used to turn the StatePart into a definitive
		/* TODO */ which has to be called to set its
		corresponding part of the state.
		A StatePart may rely on other StateParts as given by the
		`required` class attribute. If that is the case, all these
		StateParts will be fed into this method as arguments in the
		same order as `required` names.

		The default implementation returns TODO
		"""
		return self.args, partial(self.gl_func, *self.args)


class ProgramStatePart(StatePart):
	cost = 333
	gl_func = gl.glUseProgram

	def __init__(self, program: ShaderProgram) -> None:
		self.program = program
		self.args = (program.id,)


# Uniform values are technically not directly the business of OpenGL rendering state.
# But there's no other convenient way to have different drawables communicate
# when they want to modify their shader object's values.
class UniformStatePart(StatePart):
	cost = 5
	only_one = False

	def __init__(self, type_: int, location: int, value: ctypes.Array) -> None:
		self._fn = shader._uniform_setters[type_][1]
		self._count = shader._uniform_setters[type_][3]
		self._type = type_
		self._location = location
		self._c_array = value

	@classmethod
	def from_name_and_value(cls, p: ShaderProgram, n: str, v):
		# NOTE: Ye olde private pyglet access
		uniform = p._uniforms[n]
		type_ = uniform.type
		gl_type, _, _, count = shader._uniform_setters[type_]
		if count == 1:
			_c_array = (gl_type * count)(v)
		else:
			_c_array = (gl_type * count)(*v)

		return cls(type_, uniform.location, _c_array)

	def concretize(self) -> t.Tuple[t.Tuple, t.Callable[[], None]]:
		return (
			(self._location, self._type, bytes(self._c_array)),
			partial(self._fn, self._location, self._count, self._c_array),
		)


class TextureUnitStatePart(StatePart):
	cost = 5
	gl_func = gl.glActiveTexture

	def __init__(self, unit: int) -> None:
		self.args = (unit,)


class TextureStatePart(StatePart):
	cost = 66
	gl_func = gl.glBindTexture

	def __init__(self, texture: Texture) -> None:
		self.args = (texture.target, texture.id)


class SamplerBindingState(StatePart):
	cost = 5
	gl_func = gl.glBindSampler

	def __init__(self, target_unit_idx: int, sampler_name: int) -> None:
		self.args = (target_unit_idx, sampler_name)


# This thing sets up the binding from a uniform block buffer to the python UBO's
# binding index, which is set in them beforehand as a hardcoded contract with all
# the shaders in this beautiful spaghetti pile of a project.
# Precisely: WindowBlock at 0. CameraAttrs at 1.
class UBOBindingStatePart(StatePart):
	cost = 20
	gl_func = gl.glBindBufferBase
	only_one = False

	def __init__(self, ubo: UniformBufferObject) -> None:
		self._binding_idx = ubo.index
		self._buf_id = ubo.buffer.id

	def concretize(self) -> t.Tuple[t.Tuple, t.Callable[[], None]]:
		def f():
			gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, self._binding_idx, self._buf_id)

		return ((self._binding_idx, self._buf_id), f)


class EnableStatePart(StatePart):
	cost = 1
	gl_func = gl.glEnable
	only_one = False

	def __init__(self, capability: int) -> None:
		self.args = (capability,)


class BlendFuncStatePart(StatePart):
	cost = 1
	gl_func = gl.glBlendFunc

	def __init__(self, src, dest) -> None:
		self.args = (src, dest)

# https://stackoverflow.com/questions/2171085/opengl-blending-with-previous-contents-of-framebuffer
# Tamschi i love your answer so much i can not express it like oh my god
# 5 days of work with bullshit "max alpha" structures when all that could've
# been solved with a separate blend func huuhhhghghhg

class SeparateBlendFuncStatePart(StatePart):
	cost = 1
	gl_func = gl.glBlendFuncSeparate

	def __init__(self, srcc, destc, srca, desta) -> None:
		self.args = (srcc, destc, srca, desta)


StateIdentifier = t.Tuple[t.Type[StatePart], t.Tuple]


class GLState:
	"""
	Represents a specific OpenGL state.
	Used so drawables can tell the graphics backend the state they
	must be drawn in (e.g. set shader program, blend funcs etc.)
	"""

	def __init__(
		self,
		parts: t.Sequence[t.Tuple[StateIdentifier, t.Callable[[], t.Any]]],
		program: ShaderProgram | None = None,
	) -> None:
		self.parts = parts
		self.part_set: t.FrozenSet[StateIdentifier] = frozenset(ident for ident, _ in parts)
		self.program = program

	@classmethod
	def empty(cls):
		return cls((), None)

	@classmethod
	def from_state_parts(cls, program_sp: ProgramStatePart | None, *state_parts: StatePart):
		"""
		Initializes a GLState from the given StateParts.
		Note that a GLState must have a ProgramStatePart to be
		renderable.
		"""
		program: ShaderProgram | None = None if program_sp is None else program_sp.program
		parts: t.List[t.Tuple[StateIdentifier, t.Callable[[], t.Any]]] = []
		tmp_parts: t.Dict[t.Type[StatePart] | StateIdentifier, StatePart] = {}
		if program_sp is None:
			program = None
		else:
			program = program_sp.program
			i, f = program_sp.concretize()
			parts.append(((ProgramStatePart, i), f))
			tmp_parts[ProgramStatePart] = program_sp

		for part in state_parts:
			part_t = type(part)

			if isinstance(part, ProgramStatePart):
				raise ValueError("Only one program per state.")

			if part.only_one:
				if part_t in tmp_parts:
					raise ValueError(f"Duplicate StatePart for {part_t}; may only exist once!")
				# ident, func = part.concretize(*conc_args)
				ident, func = part.concretize()
				tmpkey = part_t
			else:
				# ident, func = part.concretize(*conc_args)
				ident, func = part.concretize()
				tmpkey = (part_t, ident)

			parts.append(((part_t, ident), func))
			tmp_parts[tmpkey] = part

		return cls(parts, program)

	def switch(self, new_state: GLState) -> t.List[t.Callable[[], t.Any]]:
		"""
		Emits all functions that need to be called for morphing the
		OpenGL state from this state into the new one.
		"""
		return [func for ident, func in new_state.parts if ident not in self.part_set]

	def __eq__(self, o: object) -> bool:
		if isinstance(o, GLState):
			return self.part_set == o.part_set
		return super().__eq__(o)
