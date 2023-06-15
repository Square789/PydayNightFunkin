
from math import pi, sin
import typing as t

from loguru import logger
from pyglet import gl
from pyglet.image import AbstractImage, TextureArrayRegion
from pyglet.math import Vec2

from pyday_night_funkin.core.animation import AnimationController
from pyday_night_funkin.core.animation.frames import AnimationFrame, FrameCollection
from pyday_night_funkin.core.graphics import PNFGroup
import pyday_night_funkin.core.graphics.state as s
from pyday_night_funkin.core.scene_context import SceneContext
from pyday_night_funkin.core.scene_object import WorldObject
from pyday_night_funkin.core.shaders import ShaderContainer
from pyday_night_funkin.core.utils import clamp, get_error_tex, get_pixel_tex

if t.TYPE_CHECKING:
	from pyglet.graphics.shader import UniformBufferObject
	from pyday_night_funkin.core.types import Numeric


_PNF_SPRITE_VERTEX_SHADER_SOURCE = """
#version 450

// 12 vtx attrs is totally not a sign of me doing anything wrong
// Plus, these are realistically going to be calculated 3 times more
// that needed for each sprite. Oh well, calculating them on the python
// side is out of the question, that's what I get for using this
// language.

in vec2 position;
in vec2 translate;
in vec2 offset;
in vec2 frame_offset;
in vec2 frame_dimensions;
in vec2 flip;
in vec2 scroll_factor;
in vec2 origin;
in float rotation;
in vec2 scale;
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
	vec2  GAME_DIMENSIONS;
	vec2  dimensions;
}} camera;


void main() {{
	mat4 m_camera_trans_scale = mat4(1.0);
	mat4 res_mat = mat4(1.0);
	mat4 work_mat = mat4(1.0);

	// vec2 flip = vec2(flip.x == 0.0 ? 0.0 : 1.0, flip.y == 0.0 ? 0.0 : 1.0);

	// Readds the origin and finally translates the sprite to its intended
	// position using both `translate` and `offset`.
	work_mat[3].xy = origin + translate - offset;
	res_mat *= work_mat; work_mat = mat4(1.0);      // 5TH

	// Rotates the scaled sprite around its origin.
	work_mat[0][0] =  cos(radians(rotation));
	work_mat[0][1] =  sin(radians(rotation));
	work_mat[1][0] = -sin(radians(rotation));
	work_mat[1][1] =  cos(radians(rotation));
	res_mat *= work_mat; work_mat = mat4(1.0);      // 4TH

	// Scales the sprite and subtracts the origin for next step's rotation.
	work_mat[3].xy = -origin * scale;
	work_mat[0][0] = scale.x;
	work_mat[1][1] = scale.y;
	res_mat *= work_mat; work_mat = mat4(1.0);      // 3RD

	// Applies the flipping operations, scaling the sprite by 1 or -1 and
	// translating it appropiately.
	// Turns the scaling 1.0s along the diagonal into -1.0 if applicable.
	work_mat[0][0] -= flip.x * 2.0;
	work_mat[1][1] -= flip.y * 2.0;
	work_mat[3].xy = flip * frame_dimensions;
	res_mat *= work_mat; work_mat = mat4(1.0);      // 2ND

	// Applies a simple additional frame offset.
	work_mat[3].xy = frame_offset;
	// res_mat *= work_mat; work_mat = mat4(1.0);   // 1ST
	res_mat *= work_mat;

	// Applies the translation caused by the camera and the sprite's
	// scroll factor as well as the scaling caused by the camera's zoom.
	m_camera_trans_scale[3].xy = (
		(camera.zoom * -camera.GAME_DIMENSIONS / 2.0) +
		(camera.zoom * scroll_factor * -camera.position) +
		(camera.GAME_DIMENSIONS / 2.0)
	);
	m_camera_trans_scale[0][0] = camera.zoom;
	m_camera_trans_scale[1][1] = camera.zoom;       // 6TH

	// Notes for my dumbass cause simple things like matrices will never get into my head:
	// - Matrix multiplication is associative: A*(B*C) == (A*B)*C
	// - Matrix multiplication is not commutative: A*B != B*A
	// The last matrix in a multiplication chain will be the first operation.
	// So, to scale, rotate and THEN translate something (usual sane order):
	// `gl_Position = m_trans * m_rot * m_scale * vec4(position, 0.0, 1.0);`
	// Makes sense, really.

	// The view matrix is technically not as required anymore / unused by PNF.
	// Leaving it in anyways.
	gl_Position =
		window.projection *
		window.view *
		m_camera_trans_scale *
		res_mat *
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

class PNFSpriteVertexShader:
	src = _PNF_SPRITE_VERTEX_SHADER_SOURCE

	@classmethod
	def generate(cls) -> str:
		return cls.src.format()


class PNFSpriteFragmentShader:
	src = _PNF_SPRITE_FRAGMENT_SHADER_SOURCE

	class COLOR:
		BLEND = "texture(sprite_texture, texture_coords.xy) * vertex_colors"
		SET =   "vec4(vertex_colors.rgb, texture(sprite_texture, texture_coords.xy).a)"

	@classmethod
	def generate(cls, color_behavior: str = COLOR.BLEND) -> str:
		return cls.src.format(color_behavior=color_behavior)


class Movement:
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

		self.velocity.x = vel_x
		self.velocity.y = vel_y

		return Vec2(posx_delta, posy_delta)


class PNFSprite(WorldObject):
	"""
	Pretty much *the* core scene object.
	It can show images or animations, has all the transforms such as
	position, rotation and scale and can have tweens applied to these.
	Closely copies the behavior of FlxSprite.
	"""

	shader_container = ShaderContainer(
		PNFSpriteVertexShader.generate(),
		PNFSpriteFragmentShader.generate(),
	)

	def __init__(
		self,
		image: t.Optional[AbstractImage] = None,
		x: "Numeric" = 0,
		y: "Numeric" = 0,
		blend_src = gl.GL_SRC_ALPHA,
		blend_dest = gl.GL_ONE_MINUS_SRC_ALPHA,
		context: t.Optional[SceneContext] = None,
		usage: t.Literal["dynamic", "stream", "static"] = "dynamic",
		subpixel: bool = False,
	) -> None:
		super().__init__(x, y)

		image = get_error_tex() if image is None else image

		self.animation = AnimationController(self)

		# NOTE: Copypaste of this exists at PNFSpriteContainer.__init__,
		# modify it when modifying this!
		self.movement: t.Optional[Movement] = None

		self._origin = (0, 0)
		self._offset = (0, 0)
		self._flip_x = False
		self._flip_y = False

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
		self._blend_src = blend_src
		self._blend_dest = blend_dest

		self._context = SceneContext() if context is None else context.inherit()
		self._create_interfacer()

		self.image = image

	def _build_gl_state(self, cam_ubo: "UniformBufferObject") -> s.GLState:
		return s.GLState.from_state_parts(
			s.ProgramStatePart(self.shader_container.get_program()),
			s.UBOBindingStatePart(cam_ubo),
			s.TextureUnitStatePart(gl.GL_TEXTURE0),
			s.TextureStatePart(self._texture),
			# Insanely unneccessary as uniforms are initialized to 0 anyways
			# s.UniformStatePart("sprite_texture", 0),
			s.EnableStatePart(gl.GL_BLEND),
			s.SeparateBlendFuncStatePart(
				self._blend_src, self._blend_dest, gl.GL_ONE, self._blend_dest
			)
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
			("position2f/" + usage,         None),
			("translate2f/" + usage,        (self._x, self._y) * 4),
			("offset2f/" + usage,           self._offset * 4),
			("frame_offset2f/" + usage,     None),
			("frame_dimensions2f/" + usage, None),
			("flip2B/" + usage,             (self._flip_x, self._flip_y) * 4),
			("scroll_factor2f/" + usage,    self._scroll_factor * 4),
			("origin2f/" + usage,           self._origin * 4),
			("rotation1f/" + usage,         (self._rotation,) * 4),
			(
				"scale2f/" + usage,
				(self._scale * self._scale_x, self._scale * self._scale_y) * 4
			),
			("tex_coords3f/" + usage,       self._texture.tex_coords),
			("colors4Bn/" + usage,          (*self._color, int(self._opacity)) * 4),
		)
		self._update_vertex_positions()

	def set_context(self, parent_context: SceneContext) -> None:
		"""
		This function actually doesn't set a context, it just
		modifies the existing one and takes all necessary steps for
		the sprite to be displayed in the new context.
		"""
		new_batch = parent_context.batch
		new_group = parent_context.group
		new_cams = parent_context.cameras
		old_batch = self._context.batch
		old_group = self._context.group
		old_cams = self._context.cameras

		change_batch = new_batch != old_batch
		rebuild_group = new_cams != old_cams or new_group != old_group.parent

		new_states = None
		if change_batch:
			self._context.batch = new_batch
			new_states = {cam: self._build_gl_state(cam.ubo) for cam in new_cams}

		if rebuild_group:
			self._context.cameras = new_cams
			self._context.group = PNFGroup(new_group)

		if change_batch or rebuild_group:
			self._interfacer.migrate(self._context.batch, self._context.group, new_states)

	def start_movement(
		self,
		velocity: t.Union[Vec2, t.Tuple[float, float]],
		acceleration: t.Optional[t.Union[Vec2, t.Tuple[float, float]]] = None,
	) -> None:
		if not isinstance(velocity, Vec2):
			velocity = Vec2(*velocity)

		if acceleration is None:
			acceleration = Vec2(0, 0)
		elif not isinstance(acceleration, Vec2):
			acceleration = Vec2(*acceleration)

		self.movement = Movement(velocity, acceleration)

	def stop_movement(self) -> None:
		self.movement = None

	def make_rect(self, color: t.Tuple[int, int, int, "Numeric"], w: int = 1, h: int = 1) -> None:
		"""
		Convenience method that changes the sprite to be a rectangle of
		the given color spanning by (w, h) from its current position.
		Will make a call to `recalculate_positioning`, set an extreme
		offset and set scale_x as well as scale_y.
		"""
		self.image = get_pixel_tex()
		self.scale = 1.0
		self.scale_x = w
		self.scale_y = h
		self.recalculate_positioning()
		self.rgba = color
		# no idea how good the logic on this is. Pixel origin is (.5, .5), so this should
		# get rid of off-by-one errors especially notable on rects on screen borders.
		# Sign difference because ??? projection stuff with inverted y axis who knows, this
		# seems to work
		self.offset = (-int(w // 2 + .5), -int(h // 2 - .5))

	def set_dimensions_from_frame(self) -> None:
		"""
		Sets the sprite's width and height to the currently displayed
		frame's, ignoring scale.
		"""
		self._width, self._height = self._frame.source_dimensions

	def center_offset(self) -> None:
		"""
		Sets the sprite's offset to negative half the difference of the
		currently displayed frame's dimensions and the sprite's width/
		height. The width/height is assumed to reflect the sprite's
		scale, so that the offset readjusts the error that stems from
		moving a scaled frame. [Or something like that. I think.]
		"""
		self.offset = (
			-0.5 * (self._width - self._frame.source_dimensions[0]),
			-0.5 * (self._height - self._frame.source_dimensions[1]),
		)

	def center_origin(self) -> None:
		"""
		Centers the sprite's origin to the currently displayed frame's
		midpoint. Completely ignores scaling.
		"""
		self.origin = (
			0.5 * self._frame.source_dimensions[0],
			0.5 * self._frame.source_dimensions[1],
		)

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
		self.center_offset()
		self.center_origin()

	def update(self, dt: float) -> None:
		self.animation.update(dt)

		if self.movement is not None:
			dx, dy = self.movement.update(dt)
			self.position = (self._x + dx, self._y + dy)

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
			self._interfacer.set_states(
				{camera: self._build_gl_state(camera.ubo) for camera in self._context.cameras}
			)
		else:
			self._texture = texture
		self._interfacer.set_data("tex_coords", texture.tex_coords)
		self._interfacer.set_data("frame_offset", tuple(new_frame.offset) * 4)
		self._interfacer.set_data("frame_dimensions", tuple(new_frame.source_dimensions) * 4)
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
		self._interfacer = None
		self._texture = None
		self._context = None # GC speedup, probably
		self.animation = None

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
		self.center_origin()

	@property
	def x(self) -> "Numeric":
		"""The sprite's x coordinate."""
		return self._x

	@x.setter
	def x(self, new_x: "Numeric") -> None:
		self._x = new_x
		self._interfacer.set_data("translate", (new_x, self._y) * 4)

	@property
	def y(self) -> "Numeric":
		"""The sprite's y coordinate."""
		return self._y

	@y.setter
	def y(self, new_y: "Numeric") -> None:
		self._y = new_y
		self._interfacer.set_data("translate", (self._x, new_y) * 4)

	@property
	def position(self) -> t.Tuple["Numeric", "Numeric"]:
		"""
		The sprite's position. Sets both x and y at the same time and
		should run just about 3.7% faster.
		"""
		return (self._x, self._y)

	@position.setter
	def position(self, new_position: t.Tuple["Numeric", "Numeric"]) -> None:
		self._x, self._y = new_position
		self._interfacer.set_data("translate", new_position * 4)

	@property
	def rotation(self) -> float:
		"""The sprite's rotation, in degrees."""
		return self._rotation

	@rotation.setter
	def rotation(self, new_rotation: float) -> None:
		self._rotation = new_rotation
		self._interfacer.set_data("rotation", (new_rotation,) * 4)

	@property
	def scale_x(self) -> "Numeric":
		"""
		The sprite's scale along the x axis.
		Attention: Sprites get weird with scaling and rotation when
		their scale is changed and `recalculate_positioning` is not
		called. Try `set_scale_x_and_repos` for convenience instead.
		"""
		return self._scale_x

	@scale_x.setter
	def scale_x(self, new_scale_x: "Numeric") -> None:
		self._scale_x = new_scale_x
		self._interfacer.set_data(
			"scale", (self._scale * new_scale_x, self._scale * self._scale_y) * 4
		)

	def set_scale_x_and_repos(self, new_scale_x: "Numeric") -> None:
		"""Sets scale_x and calls `recalculate_positioning`"""
		self.scale_x = new_scale_x
		self.recalculate_positioning()

	@property
	def scale_y(self) -> "Numeric":
		"""
		The sprite's scale along the y axis.
		Attention: Sprites get weird with scaling and rotation when
		their scale is changed and `recalculate_positioning` is not
		called. Try `set_scale_y_and_repos` for convenience instead.
		"""
		return self._scale_y

	@scale_y.setter
	def scale_y(self, new_scale_y: "Numeric") -> None:
		self._scale_y = new_scale_y
		self._interfacer.set_data(
			"scale", (self._scale * self._scale_x, self._scale * new_scale_y) * 4
		)

	def set_scale_y_and_repos(self, new_scale_y: "Numeric") -> None:
		"""Sets scale_y and calls `recalculate_positioning`"""
		self.scale_y = new_scale_y
		self.recalculate_positioning()

	@property
	def scale(self) -> "Numeric":
		"""
		The sprite's scale along both axes.
		Attention: Sprites get weird with scaling and rotation when
		their scale is changed and `recalculate_positioning` is not
		called. Try `set_scale_and_repos` for convenience instead.
		"""
		return self._scale

	@scale.setter
	def scale(self, new_scale: "Numeric") -> None:
		self._scale = new_scale
		self._interfacer.set_data(
			"scale",
			(new_scale * self._scale_x, new_scale * self._scale_y) * 4,
		)

	def set_scale_and_repos(self, new_scale: "Numeric") -> None:
		"""Sets scale and calls `recalculate_positioning`"""
		self.scale = new_scale
		self.recalculate_positioning()

	@property
	def origin(self) -> t.Tuple["Numeric", "Numeric"]:
		"""
		The sprite's origin.
		This is a point the sprite will be rotated and scaled around,
		measured in pixels. It is not moved by the sprite scaling,
		look into `recalculate_positioning` for that.
		"""
		return self._origin

	@origin.setter
	def origin(self, new_origin: t.Tuple["Numeric", "Numeric"]) -> None:
		self._origin = new_origin
		self._interfacer.set_data("origin", new_origin * 4)

	@property
	def offset(self) -> t.Tuple["Numeric", "Numeric"]:
		"""
		Sprite offset.
		The offset is applied at the very end of rendering, when
		rotation and scaling have all taken place.
		If animations specify offsets, this field will be set to those
		with no respect to any user-given offset.
		"""
		# Going by Flixel, technically, this is supposed to only affect
		# the hitbox, but it's flat-out used in rendering code, so that's
		# a lie.
		# Also, in FnF's source, this value is misused. offset is set
		# when frame data is set, depending on the first fucking frame in
		# a sprite sheet. this has then influenced manually set
		# per-animation offsets, that will likely break completely if
		# `updateHitbox` should ever be called. pain.
		return self._offset

	@offset.setter
	def offset(self, new_offset: t.Tuple["Numeric", "Numeric"]) -> None:
		self._offset = new_offset
		self._interfacer.set_data("offset", new_offset * 4)

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
	def visible(self) -> bool:
		"""
		Whether the sprite should be drawn.
		"""
		return self._interfacer._visible

	@visible.setter
	def visible(self, visible: bool) -> None:
		self._interfacer.set_visibility(visible)

	@property
	def flip_x(self) -> bool:
		"""
		Whether the sprite gets flipped on the x axis.
		"""
		return self._flip_x

	@flip_x.setter
	def flip_x(self, new_flip_x: bool) -> None:
		self._flip_x = new_flip_x
		self._interfacer.set_data("flip", (new_flip_x, self._flip_y) * 4)

	@property
	def flip_y(self) -> bool:
		"""
		Whether the sprite gets flipped on the y axis.
		"""
		return self._flip_y

	@flip_y.setter
	def flip_y(self, new_flip_y: bool) -> None:
		self._flip_y = new_flip_y
		self._interfacer.set_data("flip", (self._flip_x, new_flip_y) * 4)

	def _dump(self) -> None:
		print(f"x, y: {self.x}, {self.y}")
		print(f"Offset: {self.offset}")
		print(f"Origin: {self.origin}")
		print(f"Frame offset: {self._frame.offset}")
		print(f"Frame source size: {self._frame.source_dimensions}")
		print(f"w, h: {self._width}, {self._height}")
		print(f"fw, fh: {self._frame.source_dimensions}")
