
import ctypes
from functools import partial
import typing as t

from pyglet.gl import gl
from pyglet.graphics import shader

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram, UniformBufferObject


class StatePart:
	cost: int = -1
	gl_func: t.Optional[t.Callable] = None
	required: t.Sequence[t.Union["StatePart", t.Tuple["StatePart", t.Tuple]]] = ()
	# conflicts: t.Sequence["StatePart"] = () # NOTE: Something to consider for glEnable / glDisable.
	# Never using glDisable, so meh.
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

	def __init__(self, program: "ShaderProgram") -> None:
		# NOTE: Not using program.use will cause program's internal `_active` variable to not be
		# set which makes all other functions on it unusable/insecure.
		self.program = program
		self.args = (program.id,)


class UniformStatePart(StatePart):
	cost = 5
	required = (ProgramStatePart,)
	only_one = False

	def __init__(self, name: str, value: t.Any) -> None:
		self._name = name
		self.value = value
		self._c_array = None

	def concretize(self, program_sp: ProgramStatePart) -> t.Tuple[t.Tuple, t.Callable[[], None]]:
		# NOTE: Ye olde private pyglet access
		uniform = program_sp.program.uniforms[self._name]
		gl_type, gl_func, _, _, count = shader._uniform_setters[uniform.type]
		loc = uniform.location
		self._c_array = (gl_type * uniform.length)()
		if uniform.length == 1:
			self._c_array[0] = self.value
		else:
			self._c_array[:] = self.value

		return (
			(loc, count, ctypes.addressof(self._c_array)),
			partial(gl_func, loc, count, self._c_array),
		)


class TextureUnitStatePart(StatePart):
	cost = 5
	gl_func = gl.glActiveTexture

	def __init__(self, unit: int) -> None:
		self.args = (unit,)


class TextureStatePart(StatePart):
	cost = 66
	gl_func = gl.glBindTexture

	def __init__(self, texture) -> None:
		self.args = (texture.target, texture.id)


class UBOBindingStatePart(StatePart):
	cost = 20
	gl_func = gl.glUniformBlockBinding
	required = (ProgramStatePart,)
	only_one = False

	def __init__(self, ubo: "UniformBufferObject") -> None:
		self.ubo = ubo

	def concretize(self, prog_sp) -> t.Tuple[t.Tuple, t.Callable[[], None]]:
		prog_id = prog_sp.program.id
		block_idx = self.ubo.block.index
		binding_point = self.ubo.index
		buf_id = self.ubo.buffer.id

		def f():
			gl.glUniformBlockBinding(prog_id, block_idx, binding_point)
			gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, binding_point, buf_id)

		return ((prog_id, block_idx, binding_point, buf_id), f)


class EnableStatePart(StatePart):
	cost = 1
	gl_func = gl.glEnable
	only_one = False

	def __init__(self, capability: int) -> None:
		self.args = (capability,)


class BlendFuncStatePart(StatePart):
	cost = 1
	gl_func = gl.glBlendFunc
	required = ((EnableStatePart, (gl.GL_BLEND,)),)

	def __init__(self, src, dest) -> None:
		self.args = (src, dest)

# https://stackoverflow.com/questions/2171085/opengl-blending-with-previous-contents-of-framebuffer
# Tamschi i love your answer so much i can not express it like oh my god
# 5 days of work with bullshit "max alpha" structures when all that could've
# been solved with a separate blend func huuhhhghghhg

class SeparateBlendFuncStatePart(StatePart):
	cost = 1
	gl_func = gl.glBlendFuncSeparate
	required = ((EnableStatePart, (gl.GL_BLEND,)),)

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
		parts: t.List[t.Tuple[StateIdentifier, t.Callable[[], t.Any]]],
		program: t.Optional["ShaderProgram"] = None,
	) -> None:
		self.parts = parts
		self.part_set: t.Set[StateIdentifier] = {ident for ident, _ in parts}
		self.program = program

	@classmethod
	def from_state_parts(cls, *state_parts: StatePart) -> None:
		"""
		Initializes a GLState from the given StateParts.
		Note that a GLState must have a ProgramStatePart to be
		renderable.
		"""
		program: "ShaderProgram" = None
		parts: t.List[t.Tuple[StateIdentifier, t.Callable[[], t.Any]]] = []
		tmp_parts: t.Dict[t.Union[t.Type[StatePart], StateIdentifier], StatePart] = {}

		for part in state_parts:
			part_t = type(part)
			conc_args = []

			for reqp in part.required:
				if reqp not in tmp_parts:
					raise ValueError(
						f"StatePart {part} required StatePart {reqp} which was not found. "
						f"Add it to the GLState or check your StateParts' order."
					)
				conc_args.append(tmp_parts[reqp])

			if part.only_one:
				if part_t in tmp_parts:
					raise ValueError(f"Duplicate StatePart for {part_t}; may only exist once!")
				ident, func = part.concretize(*conc_args)
				tmpkey = part_t
			else:
				ident, func = part.concretize(*conc_args)
				tmpkey = (part_t, ident)

			parts.append(((part_t, ident), func))
			tmp_parts[tmpkey] = part

			if isinstance(part, ProgramStatePart):
				program = part.program

		return cls(parts, program)

	def switch(self, new_state: "GLState") -> t.List[t.Callable[[], t.Any]]:
		"""
		Emits all functions that need to be called for morphing the
		OpenGL state from this state into the new one.
		"""
		return [func for ident, func in new_state.parts if ident not in self.part_set]

	def __eq__(self, o: object) -> bool:
		if isinstance(o, GLState):
			return self.part_set == o.part_set
		return super().__eq__(o)
