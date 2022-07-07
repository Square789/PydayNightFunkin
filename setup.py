#!/usr/bin/env python

import os
import platform
import subprocess
import sys

from setuptools import find_packages, setup, Extension
from Cython.Build import cythonize
from Cython.Compiler import Options

Options.fast_fail = True

CYGL_USE = True
CYGL_HYPER_UNSAFE = False


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
		r = subprocess.run([sys.executable, "-m", "pyday_night_funkin.core.graphics.cygl.gen_gl"])
		if r.returncode != 0:
			print("gen_gl script failed.")
			sys.exit(1)

		extractor_gen_script_args = [
			sys.executable,
			"-m",
			"pyday_night_funkin.core.graphics.vertexbuffer_gen_pyobj_extractors",
		]
		if CYGL_HYPER_UNSAFE:
			extractor_gen_script_args.extend(["--", "--hyper-unsafe"])

		r = subprocess.run(extractor_gen_script_args)
		if r.returncode != 0:
			print("pyobj extractor snippet generation script failed.")
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
