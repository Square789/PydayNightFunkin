"""
This module contains a crappy copy-pasted PNFSprite alternate which
can only be controlled via a matrix.

Only used for the equally unsupported adobe atlas sprite.

Do not use tbh might remove later.
"""


import typing as t

from loguru import logger
from pyglet import gl
from pyglet.image import AbstractImage, TextureArrayRegion
from pyglet.math import Vec2

from pyday_night_funkin.core.animation import AnimationController
from pyday_night_funkin.core.animation.frames import AnimationFrame, FrameCollection
from pyday_night_funkin.core.graphics.samplers import get_sampler
import pyday_night_funkin.core.graphics.state as s
from pyday_night_funkin.core.scene_context import CamSceneContext
from pyday_night_funkin.core.scene_object import WorldObject
from pyday_night_funkin.core.shaders import ShaderContainer
from pyday_night_funkin.core.utils import get_error_tex

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import UniformBufferObject
	from pyday_night_funkin.core.types import Numeric


_PNF_MATRIX_SPRITE_VERTEX_SHADER_SOURCE = """
#version 450

in vec2 position;
in vec4 matrixa;
in vec4 matrixb;
in vec4 matrixc;
in vec4 matrixd;
in vec2 scroll_factor;
in vec3 tex_coords;
in vec4 colors;

out vec4 vertex_colors;
out vec3 texture_coords;

uniform WindowBlock {{
	mat4 projection;
	mat4 view;
}} window;

layout(std140) uniform CameraAttrs {{
	float zoom;
	vec2  position;
	vec2  dimensions;
	vec2  focus_center;
}} camera;


void main() {{
	mat4 m_camera_trans_scale = mat4(1.0);
	mat4 matrix = transpose(mat4(matrixa, matrixb, matrixc, matrixd));

	vec2 half_dimensions = camera.dimensions * 0.5;
	m_camera_trans_scale[3].xy = (
		(camera.zoom * -half_dimensions) +
		(camera.zoom * scroll_factor * -camera.position) +
		(camera.zoom * (scroll_factor - 1.0) * (camera.focus_center - half_dimensions)) +
		(half_dimensions)
	);

	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;       // 6TH

	// The view matrix is technically not as required anymore / unused by PNF.
	// Leaving it in anyways.
	gl_Position =
		window.projection *
		window.view *
		m_camera_trans_scale *
		matrix *
		vec4(position, 0.0, 1.0)
	;

	vertex_colors = colors;
	texture_coords = tex_coords;
}}
"""

_PNF_SPRITE_FRAGMENT_SHADER_SOURCE = """
#version 450

in vec4 vertex_colors;
in vec3 texture_coords;

out vec4 final_color;

uniform sampler2D sprite_texture;

void main() {{
	final_color = {color_behavior};
}}
"""

class PNFMatrixSpriteVertexShader:
	src = _PNF_MATRIX_SPRITE_VERTEX_SHADER_SOURCE

	@classmethod
	def generate(cls) -> str:
		return cls.src.format()


class PNFMatrixSpriteFragmentShader:
	src = _PNF_SPRITE_FRAGMENT_SHADER_SOURCE

	class COLOR:
		BLEND = "texture(sprite_texture, texture_coords.xy) * vertex_colors"
		SET =   "vec4(vertex_colors.rgb, texture(sprite_texture, texture_coords.xy).a)"

	@classmethod
	def generate(cls, color_behavior: str = COLOR.BLEND) -> str:
		return cls.src.format(color_behavior=color_behavior)


class PNFMatrixSprite(WorldObject):
	"""
	PNFSprite clone that does not have any controllable
	position, rotation etc. properties and instead is controlled by a single
	transform matrix in that regard.
	"""

	shader_container = ShaderContainer(
		PNFMatrixSpriteVertexShader.generate(),
		PNFMatrixSpriteFragmentShader.generate(),
	)

	def __init__(
		self,
		image: t.Optional[AbstractImage] = None,
		matrix: t.Tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
		blend_src = gl.GL_SRC_ALPHA,
		blend_dest = gl.GL_ONE_MINUS_SRC_ALPHA,
		nearest_sampling: bool = False,
		usage: t.Literal["dynamic", "stream", "static"] = "dynamic",
		subpixel: bool = False,
		context: t.Optional[CamSceneContext] = None,
	) -> None:
		super().__init__(0, 0, CamSceneContext.create_empty() if context is None else context)

		image = get_error_tex() if image is None else image

		self.animation = AnimationController(self)

		self._matrix = matrix

		self._interfacer = None
		self._color = (255, 255, 255)
		self._opacity = 255

		self._frame: t.Optional[AnimationFrame] = None
		"""The currently displayed animation frame."""

		self._texture = image.get_texture()
		"""
		The currently displayed pyglet texture.
		Should pretty much always be `self._frame.texture`.
		"""

		self._frames: t.Optional[FrameCollection] = None
		"""Frame collection frames and textures are drawn from."""

		if isinstance(image, TextureArrayRegion):
			raise NotImplementedError("Hey VSauce, Michael here. What is a TextureArrayRegion?")
			# program = sprite.get_default_array_shader()

		self._usage = usage
		self._subpixel = subpixel
		self._nearest_sampling = nearest_sampling
		self._blend_src = blend_src
		self._blend_dest = blend_dest

		self._create_interfacer()

		self.image = image

	def _build_gl_state(self, cam_ubo: "UniformBufferObject") -> s.GLState:
		return s.GLState.from_state_parts(
			s.ProgramStatePart(self.shader_container.get_program()),
			s.UBOBindingStatePart(cam_ubo),
			s.TextureUnitStatePart(gl.GL_TEXTURE0),
			s.SamplerBindingState(0, get_sampler(self._nearest_sampling)),
			s.TextureStatePart(self._texture),
			s.EnableStatePart(gl.GL_BLEND),
			s.SeparateBlendFuncStatePart(
				self._blend_src, self._blend_dest, gl.GL_ONE, self._blend_dest
			),
		)

	def _create_interfacer(self):
		#  0- - - - -3
		#  |\D>      ^
		#  A    \    E
		#  v      <C\|
		#  1----B>---2
		usage = self._usage
		self._interfacer = self._context.batch.add_indexed(
			4,
			gl.GL_TRIANGLES,
			self._context.group,
			(0, 1, 2, 0, 2, 3),
			{camera: self._build_gl_state(camera.ubo) for camera in self._context.cameras},
			("position2f/" + usage,         (self._x, self._y) * 4),
			("matrixa4f/" + usage,          (self._matrix[:4]) * 4),
			("matrixb4f/" + usage,          (self._matrix[4:8]) * 4),
			("matrixc4f/" + usage,          (self._matrix[8:12]) * 4),
			("matrixd4f/" + usage,          (self._matrix[12:16]) * 4),
			("scroll_factor2f/" + usage,    self._scroll_factor * 4),
			("tex_coords3f/" + usage,       self._texture.tex_coords),
			("colors4Bn/" + usage,          (*self._color, int(self._opacity)) * 4),
		)
		self._update_vertex_positions()

	def set_cam_context(self, new_context: CamSceneContext) -> None:
		"""
		Modifies the existing sprite context and takes all necessary
		steps for the sprite to be displayed in the new context.
		"""
		new_batch = new_context.batch
		new_group = new_context.group
		new_cams = new_context.cameras
		old_group = self._context.group
		old_cams = self._context.cameras

		change_batch = new_batch is not self._context.batch
		rebuild_group = new_group != old_group or new_cams != old_cams

		new_states = None
		if change_batch:
			self._context.batch = new_batch

		if new_group != old_group:
			self._context.group = new_group

		if new_cams != old_cams:
			self._context.cameras = new_cams
			new_states = {cam: self._build_gl_state(cam.ubo) for cam in new_cams}

		if change_batch:
			self._interfacer.change_batch(self._context.batch, self._context.group, new_states)
		elif rebuild_group:
			self._interfacer.change_group_and_or_gl_state(new_group, new_states)

	def set_context_cameras(self, new_cameras) -> None:
		self._context.cameras = tuple(new_cameras)
		self._interfacer.change_group_and_or_gl_state(
			None,
			{cam: self._build_gl_state(cam.ubo) for cam in new_cameras},
		)

	def set_context_group(self, new_group) -> None:
		self._context.group = new_group
		self._interfacer.change_group_and_or_gl_state(new_group)

	def set_dimensions_from_frame(self) -> None:
		"""
		Sets the sprite's width and height to the currently displayed
		frame's, ignoring scale.
		"""
		self._width, self._height = self._frame.source_dimensions

	def get_current_frame_dimensions(self) -> Vec2:
		"""
		Returns the currently displayed frame's source dimensions.
		No scaling, no nothing.
		"""
		return self._frame.source_dimensions

	def recalculate_positioning(self) -> None:
		"""
		Functionally the same as `FlxSprite:updateHitbox`.
		Sets the sprite's width and height to the currently displayed
		frame's (multiplied by absolute scale) and then calls
		`center_offset` and `center_origin`.
		"""
		self._width = abs(self._scale * self._scale_x) * self._frame.source_dimensions[0]
		self._height = abs(self._scale * self._scale_y) * self._frame.source_dimensions[1]

	def update(self, dt: float) -> None:
		self.animation.update(dt)

	def set_frame_by_index(self, idx: int) -> None:
		"""
		Sets the sprite's displayed frame to be frame `idx` in its
		current frame collection (`self.frames`).
		"""
		new_frame = self.frames[idx]
		self._frame = new_frame
		texture = new_frame.texture
		prev_h, prev_w = self._texture.height, self._texture.width
		if texture.id is not self._texture.id:
			self._texture = texture
			self._interfacer.change_group_and_or_gl_state(
				None,
				{camera: self._build_gl_state(camera.ubo) for camera in self._context.cameras}
			)
		else:
			self._texture = texture
		self._interfacer.set_data("tex_coords", texture.tex_coords)
		# If this is not done, screws over vertices if the texture changes
		if prev_h != texture.height or prev_w != texture.width:
			self._update_vertex_positions()

	def _update_vertex_positions(self):
		img = self._texture
		x1 = 0
		y1 = img.height
		x2 = img.width
		y2 = 0

		if img.anchor_x != 0 or img.anchor_y != 0:
			logger.warning("Ignored anchor on pyglet texture was not 0!")

		if self._subpixel:
			self._interfacer.set_data("position", (x1, y1, x2, y1, x2, y2, x1, y2))
		else:
			self._interfacer.set_data(
				"position", tuple(map(int, (x1, y1, x2, y1, x2, y2, x1, y2)))
			)

	def delete(self):
		"""
		Deletes this sprite's graphical resources.
		"""
		self._interfacer.delete()
		del self._interfacer
		del self._texture
		del self._context # GC speedup, probably
		del self.animation

	# === Simple properties and private methods below === #

	@property
	def image(self) -> AbstractImage:
		"""
		The sprite's currently displayed image, from an animation if
		one is playing.
		Note that setting an image will replace all frames on this
		sprite and destroy any existing animations.
		"""
		return self._texture

	@image.setter
	def image(self, image: AbstractImage) -> None:
		fc = FrameCollection()
		fc.add_frame(image.get_texture(), Vec2(image.width, image.height), Vec2())
		self.frames = fc

	@property
	def frames(self) -> FrameCollection:
		"""
		# TODO put documentation here
		"""
		return self._frames

	@frames.setter
	def frames(self, new_frames: FrameCollection) -> None:
		if not new_frames.frames:
			raise ValueError("Can't have empty frame collections!")

		self.animation.delete_animations()
		self._frames = new_frames
		self.set_frame_by_index(0)
		self.set_dimensions_from_frame()

	@property
	def scroll_factor(self) -> t.Tuple[float, float]:
		"""
		The sprite's scroll factor.
		Determines how hard camera movement will displace the sprite.
		Very useful for parallax effects.
		"""
		return self._scroll_factor

	@scroll_factor.setter
	def scroll_factor(self, new_sf: t.Tuple[float, float]) -> None:
		self._scroll_factor = new_sf
		self._interfacer.set_data("scroll_factor", new_sf * 4)

	def _set_rgba(self, new_rgba: t.Tuple[int, int, int, "Numeric"]) -> None:
		self._color = new_rgba[:3]
		self.opacity = new_rgba[3]
	rgba = property(None, _set_rgba)

	@property
	def color(self) -> t.Tuple[int, int, int]:
		"""
		The sprite's color tint.
		This may have wildly varying results if a special shader
		was set.
		"""
		return self._color

	@color.setter
	def color(self, new_color: t.Tuple[int, int, int]) -> None:
		self._color = new_color
		self._interfacer.set_data("colors", (*new_color, self._opacity) * 4)

	@property
	def opacity(self) -> int:
		"""
		The sprite's opacity.
		0 is completely transparent, 255 completely opaque.
		"""
		return self._opacity

	@opacity.setter
	def opacity(self, new_opacity: "Numeric") -> None:
		new_opacity = int(new_opacity)
		self._opacity = new_opacity
		self._interfacer.set_data("colors", (*self._color, new_opacity) * 4)

	@property
	def matrix(self) -> t.Tuple[float, ...]:
		return self._matrix

	@matrix.setter
	def matrix(self, new_mat: t.Tuple[float, ...]) -> None:
		self._matrix = new_mat
		self._interfacer.set_data("matrixa", new_mat[:4] * 4)
		self._interfacer.set_data("matrixb", new_mat[4:8] * 4)
		self._interfacer.set_data("matrixc", new_mat[8:12] * 4)
		self._interfacer.set_data("matrixd", new_mat[12:16] * 4)

	@property
	def visible(self) -> bool:
		"""
		Whether the sprite should be drawn.
		"""
		return self._interfacer._visible

	@visible.setter
	def visible(self, visible: bool) -> None:
		self._interfacer.set_visibility(visible)

	@property
	def nearest_sampling(self) -> bool:
		return self._nearest_sampling

	@nearest_sampling.setter
	def nearest_sampling(self, nearest_sampling: bool) -> None:
		if nearest_sampling != self._nearest_sampling:
			self._nearest_sampling = nearest_sampling
			self._interfacer.change_group_and_or_gl_state(
				None,
				{cam: self._build_gl_state(cam.ubo) for cam in self._context.cameras},
			)
