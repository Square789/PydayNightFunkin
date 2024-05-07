"""
Unfinished (hope i remember updating this in the off-chance it becomes
finished) module to support Adobe Texture Atlas Sprites.

Currently can only display a single frame of a non-compressed
``Animation.json`` with a single spritemap.
No integration to PNF's asset system rn.

Hacking this together has been made way more simple thanks to:
https://github.com/Dot-Stuff/flxanimate
https://github.com/PluieElectrique/texture-atlas-renderer
"""

from enum import IntEnum
import json
from math import sqrt
import os
import typing as t

from loguru import logger
from pyglet.math import Vec2, Vec3, Mat4

from pyday_night_funkin.core.utils import get_error_tex
from pyday_night_funkin.core.pnf_matrix_sprite import PNFMatrixSprite
from pyday_night_funkin.core.scene_context import CamSceneContext
from pyday_night_funkin.core.scene_object import WorldObject

if t.TYPE_CHECKING:
	from pyglet.image import AbstractImage


class SymbolType(IntEnum):
	GRAPHIC = 0
	MOVIE_CLIP = 1
	BUTTON = 2

	@classmethod
	def from_string(cls, v: str) -> "SymbolType":
		if v == "graphic":
			return cls.GRAPHIC
		elif v == "movieclip":
			return cls.MOVIE_CLIP
		elif v == "button":
			return cls.BUTTON

		raise ValueError(f"Bad symbol type {v!r}")


class LoopType(IntEnum):
	ONCE = 0
	LOOP = 1
	SINGLEFRAME = 2

	@classmethod
	def from_string(cls, v: str) -> "LoopType":
		if v == "playonce":  # PO
			return cls.ONCE
		elif v == "loop":  # LP
			return cls.LOOP
		elif v == "singleframe":  # ?
			return cls.SINGLEFRAME

		raise ValueError(f"Bad loop type {v!r}")


class AdobeElementBase:
	def __init__(self, matrix: Mat4) -> None:
		self.matrix = matrix


class AdobeSymbolInstance(AdobeElementBase):
	def __init__(
		self,
		matrix: Mat4,
		symbol_name: str,
		name: str,
		type_: SymbolType,
		first_frame: int,
		loop: LoopType,
		tf_point: Vec2,
	) -> None:
		super().__init__(matrix)

		self.symbol_name = symbol_name
		"""
		Name of the referred symbol, located in the related symbol dict.
		"""

		self.name = name
		"""
		Special name for this instance.
		"""

		self.type = type_
		self.first_frame = first_frame
		self.loop = loop
		self.tf_point = tf_point


class AdobeAtlasSpriteInstance(AdobeElementBase):
	def __init__(self, matrix: Mat4, name: str) -> None:
		super().__init__(matrix)

		self.atlas_sprite_name = name
		"""
		Name of the referred atlas sprite extracted from related spritemaps.
		"""


AdobeElement = t.Union[AdobeSymbolInstance, AdobeAtlasSpriteInstance]


class AdobeFrame:
	def __init__(self, index: int, duration: int, elements: t.Sequence[AdobeElement]) -> None:
		self.index = index
		self.duration = duration
		self.elements = elements


class AdobeLayer:
	def __init__(self, name: str, frames: t.Sequence[AdobeFrame]) -> None:
		self.name = name
		self.frames = frames

		x = 0
		for frame in frames:
			if frame.index != x:
				raise ValueError("Out-of-order or overlapping frames!")
			x += frame.duration

		self.length = x


class AdobeTimeline:
	def __init__(self, layers: t.Sequence[AdobeLayer]) -> None:
		self.layers = layers
		self.length = max(lyr.length for lyr in layers)


class AdobeSymbol:
	def __init__(self, name: str, timeline: AdobeTimeline) -> None:
		self.name = name
		self.timeline = timeline


class AdobeRootAnimation(AdobeSymbol):
	def __init__(self, name: str, timeline: AdobeTimeline, stage_instance: AdobeElement) -> None:
		super().__init__(name, timeline)
		self.stage_instance = stage_instance


def parse_ata_vec2(d: t.Dict):
	return Vec2(d["x"], d["y"])


def parse_ata_vec3(d: t.Dict):
	return Vec3(d["x"], d["y"], d["z"])


def parse_ata_decomp_mat4(d: t.Dict):
	return (
		parse_ata_vec3(d["Position"]),
		parse_ata_vec3(d["Rotation"]),
		parse_ata_vec3(d["Scaling"]),
	)


def parse_ata_mat4(d: t.Dict):
	return Mat4((
		d["m00"], d["m10"], d["m20"], d["m30"],
		d["m01"], d["m11"], d["m21"], d["m31"],
		d["m02"], d["m12"], d["m22"], d["m32"],
		d["m03"], d["m13"], d["m23"], d["m33"],
	))


def parse_ata_color(d: t.Dict):
	mode = d["mode"]
	al_mul = d["alphaMultiplier"]  # probably depends on mode


def parse_ata_symbol_instance(d: t.Dict) -> AdobeSymbolInstance:
	sym_name = d["SYMBOL_name"]
	inst_name = d["Instance_Name"]
	sym_type = SymbolType.from_string(d["symbolType"])

	#  NOTE: No clue whether this is right, lol
	first_frame = d.get("firstFrame", 0)
	loop = LoopType.from_string(d.get("loop", "loop"))

	tf_point = parse_ata_vec2(d["transformationPoint"])
	mat = parse_ata_mat4(d["Matrix3D"])

	# ignore decomposed matrix, we can live without it and, since it's not included in
	# compressed Animations, have to live without it
	# mat_decomp = parse_ata_decomp_mat4(d["DecomposedMatrix"])

	color = None
	if x := d.get("color"):
		color = parse_ata_color(x)

	return AdobeSymbolInstance(mat, sym_name, inst_name, sym_type, first_frame, loop, tf_point)


def parse_ata_atlas_sprite_instance(d: t.Dict) -> AdobeAtlasSpriteInstance:
	name = d["name"]
	mat = parse_ata_mat4(d["Matrix3D"])

	return AdobeAtlasSpriteInstance(mat, name)


def parse_ata_some_element(d: t.Dict) -> t.Optional[AdobeElement]:
	if x := d.get("SYMBOL_Instance"):
		return parse_ata_symbol_instance(x)
	elif x := d.get("ATLAS_SPRITE_instance"):
		return parse_ata_atlas_sprite_instance(x)
	return None


def parse_ata_frame(d: t.Dict) -> AdobeFrame:
	index = d["index"]
	duration = d["duration"]

	elements = []
	for ed in d["elements"]:
		e = parse_ata_some_element(ed)
		if e is not None:
			elements.append(e)

	return AdobeFrame(index, duration, elements)


def parse_ata_layer_frames(l: t.List) -> t.List[AdobeFrame]:
	r = []
	for d in l:
		xd = parse_ata_frame(d)
		r.append(xd)
	return r


def parse_ata_timeline_layer(d: t.Dict) -> AdobeLayer:
	name = d["Layer_name"]
	frames = parse_ata_layer_frames(d["Frames"])
	return AdobeLayer(name, frames)


def parse_ata_timeline_layers(l: t.List) -> t.List[AdobeLayer]:
	r = []
	for d in l:
		xd = parse_ata_timeline_layer(d)
		r.append(xd)
	return r


def parse_ata_timeline(d: t.Dict) -> AdobeTimeline:
	layers = parse_ata_timeline_layers(d["LAYERS"])
	return AdobeTimeline(layers)


def parse_ata_animation(d: t.Dict) -> AdobeRootAnimation:
	sym = parse_ata_symbol(d)
	si = parse_ata_some_element(d["StageInstance"])
	if si is None:
		raise ValueError("StageInstance can not be empty")

	return AdobeRootAnimation(sym.name, sym.timeline, si)


def parse_ata_symbol(d: t.Dict) -> AdobeSymbol:
	name = d["SYMBOL_name"]
	timeline = parse_ata_timeline(d["TIMELINE"])
	return AdobeSymbol(name, timeline)


def parse_ata_symbol_dictionary(d: t.Dict) -> t.Dict[str, AdobeSymbol]:
	r = {}
	for sd in d["Symbols"]:
		symbol = parse_ata_symbol(sd)
		if symbol.name in r:
			raise ValueError(f"Duplicate symbol name {symbol.name!r}")

		r[symbol.name] = symbol

	return r


def parse_ata(d: t.Dict):
	animation = parse_ata_animation(d["ANIMATION"])
	symbol_dict = parse_ata_symbol_dictionary(d["SYMBOL_DICTIONARY"])
	metadata = d["metadata"]

	return (animation, symbol_dict, metadata)


def load_json_spritemap(json_p: str):
	with open(json_p, "r", encoding="utf-8-sig") as f:
		json_d = json.load(f)

	img_p = json_d["meta"]["image"]
	if ".." in img_p or "/" in img_p:
		raise ValueError()

	import pyglet
	img = pyglet.image.load(os.path.join(os.path.dirname(json_p), img_p)).get_texture()

	region_cache = {}
	res = {}

	for d in json_d["ATLAS"]["SPRITES"]:
		if "SPRITE" not in d:
			raise ValueError("idk man")

		actual = d["SPRITE"]

		name = actual["name"]
		if name in res:
			logger.warning("duplicate name idk skipping")

		x, y, w, h = region = (actual[x] for x in ("x", "y", "w", "h"))

		if region not in region_cache:
			region_cache[region] = img.get_region(x, img.height - h - y, w, h)

		res[name] = region_cache[region]

	return res


def load_ata_info(directory: str):
	# TODO: more than 1 spritemap
	spritemap = load_json_spritemap(os.path.join(directory, "spritemap1.json"))
	
	with open(os.path.join(directory, "Animation.json"), "r", encoding="utf-8-sig") as f:
		json_d = json.load(f)

	anim, symdict, metadata = parse_ata(json_d)

	return AdobeTextureAtlasInfo(anim, symdict, metadata, spritemap)


class AdobeTextureAtlasInfo:
	def __init__(
		self,
		animation: AdobeRootAnimation,
		symbol_dict: t.Dict[str, AdobeSymbol],
		metadata: t.Dict,
		spritemap: t.Dict[str, "AbstractImage"],
	) -> None:
		self.animation = animation
		self.symbol_dict = symbol_dict
		self.metadata = metadata
		self.spritemap = spritemap

		self.symbol_dict[self.animation.name] = self.animation


# TODO: Unused, remove probably eventually maybe
def decomp_matrix(m):
	# https://github.com/mrdoob/three.js/blob/dev/src/math/Matrix4.js

	sx = Vec3(m[0], m[1], m[2]).mag
	sy = Vec3(m[4], m[5], m[6]).mag
	sz = Vec3(m[8], m[9], m[10]).mag

	a = m[10] * m[15] - m[11] * m[14]
	b = m[9] * m[15] - m[11] * m[13]
	c = m[9] * m[14] - m[10] * m[13]
	d = m[8] * m[15] - m[11] * m[12]
	e = m[8] * m[14] - m[10] * m[12]
	f = m[8] * m[13] - m[9] * m[12]
	det = (
		m[0] * (m[5] * a - m[6] * b + m[7] * c) -
		m[1] * (m[4] * a - m[6] * d + m[7] * e) +
		m[2] * (m[4] * b - m[5] * d + m[7] * f) -
		m[3] * (m[4] * c - m[5] * e + m[6] * f)
	)
	if det < 0:
		sx = -sx

	sx_inv = 1.0 / sx
	sy_inv = 1.0 / sy
	sz_inv = 1.0 / sz

	norm_rot = Mat4((
		m[0] * sx_inv, m[1] * sx_inv,  m[2] * sx_inv,  m[3],
		m[4] * sy_inv, m[5] * sy_inv,  m[6] * sy_inv,  m[7],
		m[8] * sz_inv, m[9] * sz_inv,  m[10] * sz_inv, m[11],
		m[12],         m[13],          m[14],          m[15],
	))
	# create quaternion from norm_rot:
	# https://github.com/mrdoob/three.js/blob/dev/src/math/Quaternion.js

	m11 = norm_rot[0]
	m12 = norm_rot[4]
	m13 = norm_rot[8]
	m21 = norm_rot[1]
	m22 = norm_rot[5]
	m23 = norm_rot[9]
	m31 = norm_rot[2]
	m32 = norm_rot[6]
	m33 = norm_rot[10]
	nrtrace = m11 + m22 + m33
	if nrtrace > 0:
		s = 0.5 / sqrt( nrtrace + 1.0 )
		q_w = 0.25 / s
		q_x = ( m32 - m23 ) * s
		q_y = ( m13 - m31 ) * s
		q_z = ( m21 - m12 ) * s

	elif m11 > m22 and m11 > m33:
		s = 2.0 * sqrt( 1.0 + m11 - m22 - m33 )

		q_w = ( m32 - m23 ) / s
		q_x = 0.25 * s
		q_y = ( m12 + m21 ) / s
		q_z = ( m13 + m31 ) / s

	elif m22 > m33:
		s = 2.0 * sqrt( 1.0 + m22 - m11 - m33 )

		q_w = ( m13 - m31 ) / s
		q_x = ( m12 + m21 ) / s
		q_y = 0.25 * s
		q_z = ( m23 + m32 ) / s
	else:
		s = 2.0 * sqrt( 1.0 + m33 - m11 - m22 )

		q_w = ( m21 - m12 ) / s
		q_x = ( m13 + m31 ) / s
		q_y = ( m23 + m32 ) / s
		q_z = 0.25 * s

	# with 2d transformations, q_x and q_y are assumed to be 0

	return m[3], m[7], q_w, q_z, sx, sy


class AdobeTextureAtlasSprite(WorldObject):
	def __init__(
		self,
		x = 0,
		y = 0,
		info: t.Optional[AdobeTextureAtlasInfo] = None,
		context: t.Optional[CamSceneContext] = None,
	) -> None:
		super().__init__(x, y, CamSceneContext.create_empty() if context is None else context)

		self.subsprites: t.List[WorldObject] = []

		if info is None:
			info = AdobeTextureAtlasInfo(
				AdobeRootAnimation(
					"__empty",
					AdobeTimeline([AdobeLayer("__Layer_empty", [AdobeFrame(0, 1, [])])]),
					AdobeAtlasSpriteInstance(Mat4(), "a")
				),
				{},
				{},
				{"a": get_error_tex()}
			)

		# so, first goal:
		# display this at frame 0.
		# animation contains a stageinstance, which is a single element:
		#   either a symbol or atlas instance.
		# an atlas instance would probably mean to directly display an image and be done with it,
		#   but as if it's that simple
		# a symbol instance refers back to a known symbol, usually the animation itself
		#   (in the whole two (2) Animation.jsons i've analysed so far)
		# as soon as we hit a symbol instance, we basically have to resolve it through its symbols
		# and their respective timelines until we built a tree that only has atlas sprite instances
		# as its leaves. lovely.

		def resolve_sprites(
			info: AdobeTextureAtlasInfo,
			e: AdobeElement,
			frame_idx: int,
			seen_symbols: t.Set[str],
			depth: int,
			transformation_stack: t.List[Mat4],
		):
			transformation_stack.append(e.matrix @ transformation_stack[-1])

			if isinstance(e, AdobeAtlasSpriteInstance):
				img = info.spritemap[e.atlas_sprite_name]
				spr = PNFMatrixSprite(img, tuple(transformation_stack[-1]))
				# print(f"{' ' * depth * 2}{e.atlas_sprite_name}")
				transformation_stack.pop()

				return [spr]

			sym_def = info.symbol_dict[e.symbol_name]

			# print(f"{' ' * depth * 2}{e.symbol_name:<30}")

			if e.symbol_name in seen_symbols:
				raise ValueError(f"Symbol definition cycle: {e.symbol_name!r} contains itself")
			seen_symbols.add(e.symbol_name)

			if e.loop is LoopType.LOOP:
				actual_frame_idx = (e.first_frame + frame_idx) % sym_def.timeline.length
			elif e.loop is LoopType.ONCE:
				actual_frame_idx = min(e.first_frame + frame_idx, sym_def.timeline.length - 1)
			elif e.loop is LoopType.SINGLEFRAME:
				actual_frame_idx = e.first_frame
			else:
				raise RuntimeError(f"Bad loop type {e.loop!r}")

			r = []
			for layer in reversed(sym_def.timeline.layers):
				for frame in layer.frames:
					if frame.index <= actual_frame_idx < (frame.index + frame.duration):
						# that's our frame alright
						for sube in frame.elements:
							r.extend(resolve_sprites(
								info,
								sube,
								actual_frame_idx,
								seen_symbols,
								depth + 1,
								transformation_stack,
							))
						break
				else:
					logger.trace(
						f"Layer {layer.name} in {sym_def.name} has no frame at {actual_frame_idx}"
					)

			transformation_stack.pop()
			seen_symbols.remove(e.symbol_name)

			return r

		transformation_stack = [Mat4.from_translation(Vec3(x, y, 0.0)).transpose()]
		self.subsprites.extend(
			resolve_sprites(info, info.animation.stage_instance, 0, set(), 0, transformation_stack)
		)

		# poor hack to get the sprites up and displayed
		self.set_cam_context(self._context)

	def set_cam_context(self, new_context: CamSceneContext) -> None:
		self._context = new_context
		for i, ss in enumerate(self.subsprites):
			ss.set_cam_context(self._context.inherit(i))
