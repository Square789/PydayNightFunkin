
import typing as t

from pyglet.gl import gl

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram



class AbstractStateMutator:
	def set(self) -> None:
		pass

	def get_state_descriptor(self) -> t.Any:
		pass


class ProgramStateMutator(AbstractStateMutator):
	cost = 333

	def __init__(self, program: "ShaderProgram") -> None:
		self.program = program

	def set(self) -> None:
		self.program.use()

	def get_state_descriptor(self) -> t.Any:
		return self.program.id


class TextureUnitStateMutator(AbstractStateMutator):
	cost = 5

	def __init__(self, unit) -> None:
		self.unit = unit

	def set(self) -> None:
		gl.glActiveTexture(self.unit)

	def get_state_descriptor(self) -> t.Any:
		return self.unit


class TextureStateMutator(AbstractStateMutator):
	cost = 66

	def __init__(self, texture) -> None:
		self.texture = texture

	def set(self) -> None:
		gl.glBindTexture(self.texture.target, self.texture.id)

	def get_state_descriptor(self) -> t.Any:
		return self.texture


class UBOBindingStateMutator(AbstractStateMutator):
	cost = 20

	def __init__(self, ubo) -> None:
		self.ubo = ubo

	def set(self) -> None:
		self.ubo.bind()

	def get_state_descriptor(self) -> t.Any:
		return self.ubo


class EnableStateMutator(AbstractStateMutator):
	cost = 1

	def __init__(self, capability) -> None:
		self.capability = capability

	def set(self) -> None:
		gl.glEnable(self.capability)

	def get_state_descriptor(self) -> t.Any:
		return self.capability


class BlendFuncStateMutator(AbstractStateMutator):
	cost = 1

	def __init__(self, src, dest) -> None:
		self.src = src
		self.dest = dest

	def set(self) -> None:
		gl.glBlendFunc(self.src, self.dest)

	def get_state_descriptor(self) -> t.Any:
		return (self.src, self.dest)


class PseudoStateWall:
	"""
	I know, I'm great at naming things.
	This class stores a pseudo GL state and provides methods
	to run state mutators through it.
	"""
	def __init__(self) -> None:
		self._states = {state: None for state in states}

	def switch(
		self,
		muts: t.Dict[t.Type[AbstractStateMutator], AbstractStateMutator],
	) -> t.List[t.Callable[[], None]]:
		funcs = []
		for t, m in muts.items():
			cur = m.get_state_descriptor()
			if self._states[t] == cur:
				continue
			funcs.append(m.set)
			self._states[t] = cur

		return funcs

states = [
	ProgramStateMutator, TextureUnitStateMutator, TextureStateMutator, UBOBindingStateMutator,
	EnableStateMutator, BlendFuncStateMutator
]
