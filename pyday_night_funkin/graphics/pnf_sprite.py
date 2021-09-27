
import ctypes
import typing as t

import pyglet.clock
from pyglet import gl
from pyglet import graphics
from pyglet.graphics.shader import Shader, ShaderProgram, UniformBufferObject
from pyglet.image import AbstractImage, Texture, TextureArrayRegion
from pyglet.image.animation import Animation
from pyglet import sprite

import pyday_night_funkin.constants as CNST

if t.TYPE_CHECKING:
	from pyday_night_funkin.image_loader import FrameInfoTexture
	from pyday_night_funkin.graphics.camera import Camera


class OffsetAnimationFrame():
	"""
	Similar to pyglet's AnimationFrame, except it also stores a
	per-frame offset that should be applied to its receiving sprite's
	x and y coordinates as well as a name that can be used to identify
	the frame.
	"""

	__slots__ = ("image", "duration", "frame_info", "name")

	def __init__(
		self,
		image: Texture,
		duration: float,
		frame_info: t.Tuple[int, int, int, int],
		name: str = "?"
	) -> None:
		self.image = image
		self.duration = duration
		self.frame_info = frame_info
		self.name = name

	def __repr__(self):
		return (
			f"AnimationFrame({self.image}, duration={self.duration}, "
			f"frame_info={self.frame_info})"
		)


class PNFAnimation(Animation):
	"""
	Subclasses the pyglet Animation to add the information whether it
	should be looped and its offset into it.
	It sets the last frame's duration to `None` if it should not be looped.
	"""
	def __init__(
		self,
		frames: t.Sequence[OffsetAnimationFrame],
		offset: t.Optional[t.Tuple[int, int]],
		loop: bool = False,
	):
		super().__init__(frames)

		self.offset = offset
		self.loop = loop

		if not loop:
			self.frames[-1].duration = None


PNF_SPRITE_VERTEX_SRC = """
#version 330

in vec2 translate;
in vec4 colors;
in vec3 tex_coords;
in vec2 scale;
in vec2 position;
in vec2 scroll_factor;
in float rotation;

out vec4 vertex_colors;
out vec3 texture_coords;

uniform WindowBlock {
	mat4 projection;
	mat4 view;
} window;

// Not really sure about having GAME_DIMENSIONS here
// since it's by all means a constant

layout (std140) uniform CameraAttrs {
	float zoom;
	vec2  deviance;
	vec2  GAME_DIMENSIONS;
} camera;


mat4 m_trans_scale = mat4(1.0);
mat4 m_rotation = mat4(1.0);
mat4 m_camera_trans_scale = mat4(1.0);
mat4 m_camera_pre_trans = mat4(1.0);


void main() {
	m_trans_scale[3][0] = translate.x;
	m_trans_scale[3][1] = translate.y;
	m_trans_scale[0][0] = scale.x;
	m_trans_scale[1][1] = scale.y;
	m_rotation[0][0] =  cos(-radians(rotation));
	m_rotation[0][1] =  sin(-radians(rotation));
	m_rotation[1][0] = -sin(-radians(rotation));
	m_rotation[1][1] =  cos(-radians(rotation));
	// Camera transform and zoom scale
	m_camera_trans_scale[3][0] = (camera.zoom * scroll_factor.x * camera.deviance.x) + (camera.GAME_DIMENSIONS.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * scroll_factor.y * camera.deviance.y) + (camera.GAME_DIMENSIONS.y / 2);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;
	// Camera pre-scale-transform
	m_camera_pre_trans[3][0] = -camera.GAME_DIMENSIONS.x / 2;
	m_camera_pre_trans[3][1] = -camera.GAME_DIMENSIONS.y / 2;

	gl_Position = \\
		window.projection * \\
		window.view * \\
		m_camera_trans_scale *\\
		m_camera_pre_trans *\\
		m_trans_scale * \\
		m_rotation * \\
		vec4(position, 0, 1) \\
	;

	vertex_colors = colors;
	texture_coords = tex_coords;
}
"""

PNF_SPRITE_FRAGMENT_SRC = """
#version 150 core

in vec4 vertex_colors;
in vec3 texture_coords;

out vec4 final_colors;

uniform sampler2D sprite_texture;


void main() {
	final_colors = texture(sprite_texture, texture_coords.xy) * vertex_colors;
}
"""

class _PNFSpriteShaderContainer():
	def __init__(self) -> None:
		self.prog = None

	def get_program(self) -> ShaderProgram:
		"""
		Returns the program associated with PNFSprites.
		"""
		if self.prog is None:
			self._compile()
		return self.prog

	def get_camera_ubo(self) -> UniformBufferObject:
		"""
		Returns a new Uniform Buffer Object for the shader program's
		`CameraAttrs` uniform block, which will bind at the binding
		index the program expects.
		"""
		ubo = self.get_program().uniform_blocks["CameraAttrs"].create_ubo(1)
		# HACK: WARNING OH GOD WHY
		# HACK: I have to re-emphasize, this right here?
		# This is cancer [insert papa franku copypasta here]
		# Relies on the std140 layout specifier and patches the UBO with
		# a hardcoded alignment structure just for it.
		class _CA_struct(ctypes.Structure):
			_fields_ = [
				("zoom", ctypes.c_float),
				("_padding0", ctypes.c_float * 1),
				("deviance", ctypes.c_float * 2),
				("GAME_DIMENSIONS", ctypes.c_float * 2),
			]

		ubo.view = _CA_struct()
		ubo._view_ptr = ctypes.pointer(ubo.view)
		return ubo

	def _compile(self) -> None:
		"""
		Compiles and sets up the program.
		"""
		vertex_shader = Shader(PNF_SPRITE_VERTEX_SRC, "vertex")
		fragment_shader = Shader(PNF_SPRITE_FRAGMENT_SRC, "fragment")
		self.prog = ShaderProgram(vertex_shader, fragment_shader)
		# Window block binds itself to 0 and is a pain to control outside of
		# the actual window class, so just source it from binding point 0
		gl.glUniformBlockBinding(self.prog.id, self.prog.uniform_blocks["WindowBlock"].index, 0)
		# Source camera attributes from binding point 1
		gl.glUniformBlockBinding(self.prog.id, self.prog.uniform_blocks["CameraAttrs"].index, 1)

pnf_sprite_shader_container = _PNFSpriteShaderContainer()


class PNFSpriteGroup(sprite.SpriteGroup):
	def __init__(self, sprite: "PNFSprite", *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self.sprite = sprite

	def set_state(self):
		self.program.use()
		self.sprite.camera.ubo.bind()

		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(self.texture.target, self.texture.id)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(self.blend_src, self.blend_dest)

	def unset_state(self):
		gl.glDisable(gl.GL_BLEND)
		gl.glBindTexture(self.texture.target, 0)

		self.program.stop()


class PNFSprite(sprite.Sprite):
	"""
	TODO doc

	WARNING: This subclass meddles with many underscore-prepended
	attributes of the standard pyglet Sprite, which may completely
	break it in any other pyglet releases.
	"""
	def __init__(
		self,
		camera: "Camera",
		image: t.Optional[t.Union[PNFAnimation, AbstractImage]] = None,
		x = 0,
		y = 0,
		blend_src = gl.GL_SRC_ALPHA,
		blend_dest = gl.GL_ONE_MINUS_SRC_ALPHA,
		batch = None,
		group = None,
		usage = "dynamic",
		subpixel = False,
		program = None,
	) -> None:
		image = CNST.ERROR_TEXTURE if image is None else image

		self._animations: t.Dict[str, PNFAnimation] = {}
		self._animation_base_box = None
		self._animation_frame_offset = (0, 0)
		self._scroll_factor = (1.0, 1.0)
		self.current_animation: t.Optional[str] = None
		self.camera = camera

		self._x = x
		self._y = y

		if isinstance(image, PNFAnimation):
			self._texture = image.frames[0].image.get_texture()
		else:
			self._texture = image.get_texture()

		if isinstance(image, TextureArrayRegion):
			raise NotImplementedError("What's the deal with TextureArrayRegions?")
			program = sprite.get_default_array_shader()
		else:
			program = pnf_sprite_shader_container.get_program()

		self._batch = batch or graphics.get_default_batch()
		self._group = PNFSpriteGroup(self, self._texture, blend_src, blend_dest, program, parent = group)
		self._usage = usage
		self._subpixel = subpixel
		self._create_vertex_list()

		self.image = image

	def _apply_post_animate_offset(self) -> None:
		"""
		"Swaps out" the current animation frame offset with the new
		one. The new one is calculated in this method using the current
		animation frame, the sprite's scale and the animation base box.
		"""
		fix, fiy, fiw, fih = self._animation.frames[self._frame_index].frame_info
		nx = round(
			(fix - (self._animation_base_box[0] - fiw) // 2) *
			self._scale * self._scale_x
		)
		ny = round(
			(fiy - (self._animation_base_box[1] - fih) // 2) *
			self._scale * self._scale_y
		)
		new_frame_offset = (nx, ny)
		self.x += self._animation_frame_offset[0] - nx
		self.y += self._animation_frame_offset[1] - ny
		self._animation_frame_offset = new_frame_offset

	def _set_animation_base_box(
		self,
		what: t.Union[PNFAnimation, OffsetAnimationFrame, t.Tuple[int, int]],
	) -> None:
		if not isinstance(what, tuple):
			if not isinstance(what, OffsetAnimationFrame):
				if not isinstance(what, PNFAnimation):
					raise TypeError("Invalid type.")
				frame = what.frames[0]
			else:
				frame = what
			new_bb = (
				frame.frame_info[2] - frame.frame_info[0],
				frame.frame_info[3] - frame.frame_info[1],
			)
		else:
			new_bb = what
		self._animation_base_box = new_bb

	def _create_vertex_list(self):
		usage = self._usage
		self._vertex_list = self._batch.add_indexed(
			4, gl.GL_TRIANGLES, self._group, [0, 1, 2, 0, 2, 3],
			"position2f/" + usage,
			(
				"colors4Bn/" + usage,
				(*self._rgb, int(self._opacity)) * 4
			),
			(
				"translate2f/" + usage,
				(self._x, self._y) * 4
			),
			(
				"scale2f/" + usage,
				(self._scale * self._scale_x, self._scale * self._scale_y) * 4
			),
			(
				"rotation1f/" + usage,
				(self._rotation,) * 4
			),
			(
				"scroll_factor2f/" + usage,
				self._scroll_factor * 4
			),
			(
				"tex_coords3f/" + usage,
				self._texture.tex_coords
			),
		)
		self._update_position()

	def add_animation(
		self,
		name: str,
		anim_data: t.Union[PNFAnimation, t.Sequence["FrameInfoTexture"]],
		fps: float = 24.0,
		loop: bool = False,
		offset: t.Optional[t.Tuple[int, int]] = None,
	) -> None:
		if fps <= 0:
			raise ValueError("FPS can't be equal to or less than 0!")

		spf = 1.0 / fps
		if isinstance(anim_data, PNFAnimation):
			self._animations[name] = anim_data
		else:
			frames = [
				OffsetAnimationFrame(tex.texture, spf, tex.frame_info, name)
				for tex in anim_data
			]
			self._animations[name] = PNFAnimation(frames, offset, loop)
		if self._animation_base_box is None:
			self._set_animation_base_box(self._animations[name])

	def play_animation(self, name: str) -> None:
		self.image = self._animations[name]
		self.current_animation = name

	def screen_center(self, screen_dims: t.Tuple[int, int]) -> None:
		"""
		Sets the sprite's world position so that it is centered 
		on screen. (Ignoring camera and scroll factors)
		"""
		self.x = (screen_dims[0] // 2) - self.width
		self.y = (screen_dims[1] // 2) - self.height

	@property
	def scroll_factor(self) -> t.Tuple[float, float]:
		return self._scroll_factor

	@scroll_factor.setter
	def scroll_factor(self, new_sf: t.Tuple[float, float]) -> None:
		self._scroll_factor = new_sf
		self._vertex_list.scroll_factor[:] = new_sf * 4

	@property
	def image(self) -> t.Union[PNFAnimation, AbstractImage]:
		if self._animation is not None:
			return self._animation
		return self._texture

	@image.setter
	def image(self, image: t.Union[PNFAnimation, AbstractImage]) -> None:
		if self._animation is not None:
			pyglet.clock.unschedule(self._animate)
			# Remove the current animation frame's offset (would've been done by self._animate)
			self.x += self._animation_frame_offset[0]
			self.y += self._animation_frame_offset[1]
			self._animation_frame_offset = (0, 0)
			# Remove the animation's general offset
			if self._animation.offset is not None:
				self.x += self._animation.offset[0]
				self.y += self._animation.offset[1]
			self._animation = None
			self.current_animation = None

		if isinstance(image, PNFAnimation):
			self._animation = image
			self._frame_index = 0
			# Apply the animation's general offset
			if self._animation.offset is not None:
				self.x -= self._animation.offset[0]
				self.y -= self._animation.offset[1]
			# Set first frame and apply its offset
			if self._animation.offset is not None:
				self._set_animation_base_box(self._animation)
			self._set_texture(image.frames[0].image.get_texture())
			self._apply_post_animate_offset()
			self._next_dt = image.frames[0].duration
			if len(image.frames) == 1:
				self._next_dt = None
			if self._next_dt is not None:
				pyglet.clock.schedule_once(self._animate, self._next_dt)
		else:
			self._set_texture(image.get_texture())

	def _animate(self, dt: float) -> None:
		# Disgusting override of underscore method, required to set the
		# sprite's position on animation.
		super()._animate(dt)
		self._apply_post_animate_offset()

	# === Below methods are largely copy-pasted from the superclass sprite === #

	def _set_texture(self, texture):
		prev_h, prev_w = self._texture.height, self._texture.width
		if texture.id is not self._texture.id:
			self._group = PNFSpriteGroup(
				self, texture, self._group.blend_src, self._group.blend_dest,
				self._group.program, 0, self._group.parent
			)
			self._vertex_list.delete()
			self._texture = texture
			self._create_vertex_list()
		else:
			self._vertex_list.tex_coords[:] = texture.tex_coords
		self._texture = texture
		# NOTE: If not done, screws over vertices if the texture changes
		# dimension thanks to top left coords; no idea if should be done
		if prev_h != texture.height or prev_w != texture.width:
			self._update_position()

	def _update_position(self):
		# Contains some manipulations to creation to the
		# vertex array since otherwise it would be displayed
		# upside down
		if not self._visible:
			self._vertex_list.position[:] = (0, 0, 0, 0, 0, 0, 0, 0)
		else:
			img = self._texture
			x1 = -img.anchor_x
			y1 = -img.anchor_y + img.height
			x2 = -img.anchor_x + img.width
			y2 = -img.anchor_y
			verticies = (x1, y1, x2, y1, x2, y2, x1, y2)

			if not self._subpixel:
				self._vertex_list.position[:] = tuple(map(int, verticies))
			else:
				self._vertex_list.position[:] = verticies
