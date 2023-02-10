#!/usr/bin/env python3

import os
import platform
from setuptools import find_packages, setup, Extension
import subprocess
import sys
import typing as t

from Cython.Build import cythonize
from Cython.Compiler import Options
Options.fast_fail = True

load_dotenv: t.Optional[t.Callable] = None
try:
	from dotenv import load_dotenv # type: ignore
except ImportError:
	pass

if load_dotenv is not None:
	load_dotenv()

def _convert_bool_env_var(v: t.Optional[str]) -> bool:
	if v == "0":
		return False
	return bool(v)

CYGL_USE = _convert_bool_env_var(os.getenv("PNF_CYGL_USE", "1"))
CYGL_HYPER_UNSAFE = _convert_bool_env_var(os.getenv("PNF_CYGL_HYPER_UNSAFE", "0"))
CYGL_GL_XML_PATH = os.getenv("PNF_CYGL_GL_XML_PATH", None)


def make_gen_script_args(module: str) -> t.List[str]:
	return [sys.executable, module + ".py", "--"]


if __name__ == "__main__":
	ECA = []
	if platform.system() == "Windows":
		if "64" in os.environ["PROCESSOR_ARCHITECTURE"]:
			ECA = ["-DMS_WIN64"]

	extensions = [
		Extension(
			name = "pyday_night_funkin.core.stb_vorbis.stb_vorbis",
			sources = ["pyday_night_funkin/core/stb_vorbis/stb_vorbis.pyx"],
			extra_compile_args = ECA,
		),
		Extension(
			name = "pyday_night_funkin.core.almost_xml_parser.almost_xml_parser",
			sources = ["pyday_night_funkin/core/almost_xml_parser/almost_xml_parser.pyx"],
			extra_compile_args = ECA,
		),
		Extension(
			name = "pyday_night_funkin.core.graphics.allocation",
			sources = ["pyday_night_funkin/core/graphics/allocation.pyx"],
			extra_compile_args = ECA,
		),
	]

	if CYGL_USE:
		gl_gen_args = make_gen_script_args("pyday_night_funkin/core/graphics/cygl/gl_gen")
		if CYGL_GL_XML_PATH is not None:
			gl_gen_args.extend(["--gl-xml-path", CYGL_GL_XML_PATH])
		r = subprocess.run(gl_gen_args)
		if r.returncode != 0:
			print("gl generation script failed.")
			sys.exit(1)

		vtxbuf_gen_args = make_gen_script_args("pyday_night_funkin/core/graphics/vertexbuffer_gen")
		if CYGL_HYPER_UNSAFE:
			vtxbuf_gen_args.append("--hyper-unsafe")
		r = subprocess.run(vtxbuf_gen_args)
		if r.returncode != 0:
			print("vertexbuffer generation script failed.")
			sys.exit(1)

		extensions.extend((
			Extension(
				name = "pyday_night_funkin.core.graphics.cygl.gl",
				sources = ["pyday_night_funkin/core/graphics/cygl/gl.pyx"],
				extra_compile_args = ECA,
			),
			Extension(
				name = "pyday_night_funkin.core.graphics.vertexbuffer",
				sources = ["pyday_night_funkin/core/graphics/vertexbuffer.pyx"],
				extra_compile_args = ECA,
			),
		))

	setup(
		name = "PydayNightFunkin",
		packages = find_packages("pyday_night_funkin"),
		ext_modules = cythonize(extensions, language_level=3),
	)
