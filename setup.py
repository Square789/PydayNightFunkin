
from setuptools import find_packages, setup, Extension
from Cython.Build import cythonize
from Cython.Compiler import Options

Options.fast_fail = True

extensions = [
	Extension(
		name = "pyday_night_funkin.core.stb_vorbis.stb_vorbis",
		sources = ["pyday_night_funkin/core/stb_vorbis/stb_vorbis.pyx"],
		extra_compile_args = ["-DMS_WIN64"],
	),
	Extension(
		name = "pyday_night_funkin.core.almost_xml_parser.almost_xml_parser",
		sources = ["pyday_night_funkin/core/almost_xml_parser/almost_xml_parser.pyx"],
		extra_compile_args = ["-DMS_WIN64"],
	),
]

setup(
	name = "PydayNightFunkin",
	packages = find_packages("pyday_night_funkin"),
	ext_modules = cythonize(extensions, language_level = 3),
)
