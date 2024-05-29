"""
Very rudimentary sampler module.

Contains ``get_sampler``, which (creates and) delivers a sampler object stored
on pyglet's object space.
"""

import ctypes

import pyglet
from pyglet.gl import gl


# NOTE: Overkill for PNF, don't bother
# class SamplerKey:
# 	__slots__ = (
# 		"min_filter",
# 		"max_filter",
# 		"min_lod",
# 		"max_lod",
# 		"texture_wrap_s",
# 		"texture_wrap_t",
# 		"texture_wrap_r",
# 		"border_color",
# 		"comp_mode",
# 		"comp_func",
# 	)


def get_sampler(nearest_sampling: bool) -> int:
	key = nearest_sampling

	space = pyglet.gl.current_context.object_space
	if hasattr(space, "pnf_samplers"):
		if key in space.pnf_samplers:
			return space.pnf_samplers[key]
	else:
		space.pnf_samplers = {}

	sampler_id = gl.GLuint()
	gl.glGenSamplers(1, ctypes.byref(sampler_id))

	f = gl.GL_NEAREST if nearest_sampling else gl.GL_LINEAR
	gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, f)
	gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, f)

	space.pnf_samplers[key] = sampler_id.value
	return sampler_id.value
