
import ctypes
from time import time
import typing as t

import pyglet.clock
from pyglet import gl
from pyglet import graphics
from pyglet.graphics.shader import Shader, ShaderProgram, UniformBufferObject
from pyglet.image import AbstractImage, TextureArrayRegion
from pyglet.math import Vec2
from pyglet import sprite

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.tweens import TWEEN_ATTR
from pyday_night_funkin.graphics.pnf_animation import AnimationController, PNFAnimation
from pyday_night_funkin.utils import clamp

if t.TYPE_CHECKING:
	from pyday_night_funkin.graphics.camera import Camera


_TWEEN_ATTR_NAME_MAP = {
	TWEEN_ATTR.X: "x",
	TWEEN_ATTR.Y: "y",
	TWEEN_ATTR.ROTATION: "rotation",
	TWEEN_ATTR.OPACITY: "opacity",
	TWEEN_ATTR.SCALE: "scale",
	TWEEN_ATTR.SCALE_X: "scale_x",
	TWEEN_ATTR.SCALE_Y: "scale_y",
}


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
	vec2  position;
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
	m_camera_trans_scale[3][0] = (camera.zoom * scroll_factor.x * -camera.position.x) + (camera.GAME_DIMENSIONS.x / 2);
	m_camera_trans_scale[3][1] = (camera.zoom * scroll_factor.y * -camera.position.y) + (camera.GAME_DIMENSIONS.y / 2);
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
	// if (vertex_colors.a < 0.01) {
	// 	discard;
	// }

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
				("position", ctypes.c_float * 2),
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


class Movement():
	__slots__ = ("velocity", "acceleration")
	
	def __init__(self, velocity: Vec2, acceleration: Vec2) -> None:
		self.velocity = velocity
		self.acceleration = acceleration

	# Dumbed down case of code shamelessly stolen from https://github.com/HaxeFlixel/
	# flixel/blob/e3c3b30f2f4dfb0486c4b8308d13f5a816d6e5ec/flixel/FlxObject.hx#L738
	def update(self, dt: float) -> Vec2:
		acc_x, acc_y = self.acceleration
		vel_x, vel_y = self.velocity

		vel_delta = 0.5 * acc_x * dt
		vel_x += vel_delta
		posx_delta = vel_x * dt
		vel_x += vel_delta

		vel_delta = 0.5 * acc_y * dt
		vel_y += vel_delta
		posy_delta = vel_y * dt
		vel_y += vel_delta

		self.velocity = Vec2(vel_x, vel_y)

		return Vec2(posx_delta, posy_delta)

class Tween():
	__slots__ = (
		"tween_func", "start_time", "stop_time", "duration", "cur_time",
		"attr_map", "on_complete", "stopped"
	)

	def __init__(
		self,
		tween_func: t.Callable,
		start_time: float,
		duration: float,
		cur_time: float,
		attr_map: t.Dict[str, t.Tuple[t.Any, t.Any]],
		on_complete: t.Optional[t.Callable[[], t.Any]] = None,
	) -> None:
		self.tween_func = tween_func
		self.start_time = start_time
		self.stop_time = start_time + duration
		self.duration = duration
		self.cur_time = cur_time
		self.attr_map = attr_map
		self.on_complete = on_complete

	def update(self, dt: float) -> t.Dict[str, t.Any]:
		self.cur_time += dt
		progress = self.tween_func(
			(
				clamp(self.cur_time, self.start_time, self.stop_time) -
				self.start_time
			) / self.duration
		)

		return {
			attr_name: v_ini + v_diff * progress
			for attr_name, (v_ini, v_diff) in self.attr_map.items()
		}

	def is_finished(self) -> bool:
		return self.cur_time >= self.stop_time


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
		image: t.Optional[AbstractImage] = None,
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

		self.animation = AnimationController()
		self.camera = camera

		self.movement: t.Optional[Movement] = None
		self.tweens: t.List[Tween] = []

		self._x = x
		self._y = y
		self._scroll_factor = (1.0, 1.0)

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

	def _create_vertex_list(self):
		usage = self._usage
		self._vertex_list = self._batch.add_indexed(
			4, gl.GL_TRIANGLES, self._group, [0, 1, 2, 0, 2, 3],
			"position2f/" + usage,
			("colors4Bn/" + usage, (*self._rgb, int(self._opacity)) * 4),
			("translate2f/" + usage, (self._x, self._y) * 4),
			("scale2f/" + usage,
				(self._scale * self._scale_x, self._scale * self._scale_y) * 4),
			("rotation1f/" + usage, (self._rotation, ) * 4),
			("scroll_factor2f/" + usage, self._scroll_factor * 4),
			("tex_coords3f/" + usage, self._texture.tex_coords),
		)
		self._update_position()

	def screen_center(self, screen_dims: t.Tuple[int, int]) -> None:
		"""
		Sets the sprite's world position so that it is centered 
		on screen. (Ignoring camera and scroll factors)
		"""
		self.x = (screen_dims[0] // 2) - self.width
		self.y = (screen_dims[1] // 2) - self.height

	def get_midpoint(self) -> Vec2:
		"""
		Returns the middle point of this sprite, based on its current
		texture and world position.
		"""
		# Not using the width / height properties since they return
		# incorrect values for negative scaling
		return Vec2(
			self._x + self._texture.width * self._scale_x * self._scale * 0.5,
			self._y + self._texture.height * self._scale_y * self._scale * 0.5,
		)

	def start_tween(
		self,
		tween_func: t.Callable[[float], float],
		attributes: t.Dict[TWEEN_ATTR, t.Any],
		duration: float,
		on_complete: t.Callable[[], t.Any] = None,
		start_delay: float = 0.0,
	) -> Tween:
		"""
		# TODO write some very cool doc
		"""
		if start_delay < 0.0:
			raise ValueError("Can't start a tween in the past!")

		if start_delay:
			pyglet.clock.schedule_once(
				lambda _: self.start_tween(tween_func, attributes, duration, on_complete),
				start_delay,
			)
			return

		# 0: initial value; 1: difference
		attr_map = {}
		for attribute, target_value in attributes.items():
			attribute_name = _TWEEN_ATTR_NAME_MAP[attribute]
			initial_value = getattr(self, attribute_name)
			attr_map[attribute_name] = (initial_value, target_value - initial_value)

		start_time = time()

		t = Tween(
			tween_func,
			start_time = start_time,
			duration = duration,
			cur_time = start_time,
			attr_map = attr_map,
			on_complete = on_complete,
		)

		self.tweens.append(t)

		return t

	def start_movement(
		self,
		velocity: t.Union[Vec2, t.Tuple[float, float]],
		acceleration: t.Optional[t.Union[Vec2, t.Tuple[float, float]]] = None,
	) -> None:
		if not isinstance(velocity, Vec2):
			velocity = Vec2(*velocity)

		if acceleration is not None and not isinstance(acceleration, Vec2):
			acceleration = Vec2(*acceleration)

		self.movement = Movement(velocity, acceleration)

	def stop_movement(self) -> None:
		self.movement = None

	# Unfortunately, the name `update` clashes with sprite, so have
	# this as a certified code smell
	def update_sprite(self, dt: float) -> None:
		self.animation.update(dt)
		if (new_frame := self.animation.query_new_frame()) is not None:
			self._set_texture(new_frame)

		if (new_offset := self.animation.query_new_offset()) is not None:
			self.update(
				x = self._x + (new_offset[0] * self._scale * self._scale_x),
				y = self._y + (new_offset[1] * self._scale * self._scale_y),
			)

		if self.movement is not None:
			dx, dy = self.movement.update(dt)
			self.update(x = self.x + dx, y = self.y + dy)

		finished_tweens = []
		for tween in self.tweens:
			if tween.is_finished():
				finished_tweens.append(tween)
			else:
				for attr, v in tween.update(dt).items():
					setattr(self, attr, v)

		for tween in finished_tweens:
			if tween.on_complete is not None:
				tween.on_complete()
			try:
				self.tweens.remove(tween)
			except ValueError:
				pass

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
		if isinstance(image, PNFAnimation):
			raise RuntimeError(
				"Please play animations via the sprite's animation controller: "
				"`sprite.animation.play()`"
			)

		self.animation.stop()
		self._set_texture(image.get_texture())

	def _animate(self, dt: float) -> None:
		raise RuntimeError(
			"For PNFSprites and its subclasses, the animation controller must "
			"be used instead of pyglet's clock-based animation!"
		)

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
		# dimension thanks to top left coords
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

			if self._subpixel:
				self._vertex_list.position[:] = (x1, y1, x2, y1, x2, y2, x1, y2)
			else:
				self._vertex_list.position[:] = tuple(map(int, (x1, y1, x2, y1, x2, y2, x1, y2)))
