
from setuptools import find_packages, setup, Extension
from Cython.Build import cythonize
from Cython.Compiler import Options

Options.fast_fail = True

extensions = [
	Extension(
		name = "pyday_night_funkin.stb_vorbis",
		sources = ["stb_vorbis/__init__.pyx"],
		extra_compile_args = ["-DMS_WIN64"],
	),
	Extension(
		name = "pyday_night_funkin.almost_xml_parser",
		sources = ["pyday_night_funkin/almost_xml_parser.pyx"],
		extra_compile_args = ["-DMS_WIN64"],
	),
]

setup(
	name = "PydayNightFunkin",
	packages = find_packages("pyday_night_funkin"),
	ext_modules = cythonize(extensions, language_level = 3),
)
