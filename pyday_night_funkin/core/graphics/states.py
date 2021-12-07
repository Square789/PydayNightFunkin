
import typing as t

from pyglet.gl import gl

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import ShaderProgram


class AbstractState:
	def set(self) -> None:
		pass

	def get_state_descriptor(self) -> t.Any:
		pass


class ProgramState(AbstractState):
	cost = 333

	def __init__(self, program: "ShaderProgram") -> None:
		self.program = program

	def set(self) -> None:
		self.program.use()

	def get_state_descriptor(self) -> t.Any:
		return self.program.id


class TextureUnitState(AbstractState):
	cost = 5

	def __init__(self, unit) -> None:
		self.unit = unit

	def set(self) -> None:
		gl.glActiveTexture(self.unit)

	def get_state_descriptor(self) -> t.Any:
		return self.unit


class TextureState(AbstractState):
	cost = 66

	def __init__(self, texture) -> None:
		self.texture = texture

	def set(self) -> None:
		gl.glBindTexture(self.texture.target, self.texture.id)

	def get_state_descriptor(self) -> t.Any:
		return self.texture


class UBOBindingState(AbstractState):
	cost = 20

	def __init__(self, ubo) -> None:
		self.ubo = ubo

	def set(self) -> None:
		self.ubo.bind()

	def get_state_descriptor(self) -> t.Any:
		return self.ubo


class EnableState(AbstractState):
	cost = 1

	def __init__(self, capability) -> None:
		self.capability = capability

	def set(self) -> None:
		gl.glEnable(self.capability)

	def get_state_descriptor(self) -> t.Any:
		return self.capability


class BlendFuncState(AbstractState):
	cost = 1

	def __init__(self, src, dest) -> None:
		self.src = src
		self.dest = dest

	def set(self) -> None:
		gl.glBlendFunc(self.src, self.dest)

	def get_state_descriptor(self) -> t.Any:
		return (self.src, self.dest)


states = [
	ProgramState, TextureUnitState, TextureState, UBOBindingState,
	EnableState, BlendFuncState
]
