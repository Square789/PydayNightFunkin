
from collections import defaultdict
from pathlib import Path
import re
import typing as t
from xml.etree import ElementTree

from loguru import logger
import pyglet
from pyglet.image import Texture


_IMAGE_CACHE = {}

RE_SPLIT_ANIMATION_NAME = re.compile(r"^(.*)(\d{4})$")

class FrameInfoTexture():
	"""
	Composite class to store the special per-frame offsets found in
	the xml files alongside a Texture (or TextureRegion).
	"""
	def __init__(
		self,
		texture: Texture,
		has_frame_info: bool,
		# dumb type but should make the intended use clear
		frame_info: t.Optional[t.Tuple[int, int, int, int]] = None,
	) -> None:
		self.texture = texture
		self.has_frame_info = has_frame_info
		self.frame_info = frame_info \
			if has_frame_info and frame_info is not None \
			else (0, 0, texture.width, texture.height)


def load_image(path: Path) -> pyglet.image.AbstractImage:
	cache_key = str(path)
	if cache_key not in _IMAGE_CACHE:
		_IMAGE_CACHE[cache_key] = pyglet.image.load(str(path))
	return _IMAGE_CACHE[cache_key]

def load_animation_frames_from_xml(xml_path: Path) -> t.Dict[str, t.List[FrameInfoTexture]]:
	with xml_path.open("r", encoding = "utf-8") as fp:
		et = ElementTree.parse(fp)

	texture_atlas = et.getroot() # Should be a TextureAtlas node
	texture_region_cache = {}
	spritesheet_path = xml_path.parent / texture_atlas.attrib["imagePath"]
	atlas_surface: Texture = load_image(spritesheet_path).get_texture() # type: ignore

	frame_sequences = defaultdict(lambda: [])
	for sub_texture in texture_atlas:
		if sub_texture.tag != "SubTexture":
			logger.warning(f"Expected 'SubTexture' tag, got {sub_texture.tag!r}. Skipping.")
			continue

		name, x, y, w, h, fx, fy, fw, fh = (
			sub_texture.attrib.get(k) for k in (
				"name", "x", "y", "width", "height", "frameX", "frameY", "frameWidth",
				"frameHeight"
			)
		)
		region = (x, y, w, h)
		frame_vars = (fx, fy, fw, fh)

		if (
			name is None or any(i is None for i in region) or (
				any(i is None for i in frame_vars) and
				any(i is not None for i in frame_vars)
			) # this sucks; basically none of the first five fields may be None and either
			#   all or none of the frame_vars must be None.
		):
			logger.warning(f"{(name, region, frame_vars)} Invalid attributes for SubTexture entry. Skipping.")
			continue

		if (match_res := RE_SPLIT_ANIMATION_NAME.match(name)) is None:
			logger.warning(f"Invalid SubTexture name in {xml_path.name}: {name!r}")
			continue

		animation_name = match_res[1]
		frame_id = int(match_res[2])
		if frame_id > len(frame_sequences[animation_name]):
			logger.warning(
				f"Frames for animation {animation_name!r} inconsistent: current is "
				f"frame {frame_id}, but only {len(frame_sequences[animation_name])} frames "
				f"exist so far."
			)

		x, y, w, h = region = (int(e) for e in region)
		frame_vars = tuple(None if e is None else int(e) for e in frame_vars)
		if region not in texture_region_cache:
			texture_region_cache[region] = atlas_surface.get_region(
				x, atlas_surface.height - h - y,
				w, h,
			)
		has_frame_vars = frame_vars[0] is not None
		frame_sequences[animation_name].append(
			FrameInfoTexture(texture_region_cache[region], has_frame_vars, frame_vars)
		)

	return dict(frame_sequences) # Don't return a defaultdict!
