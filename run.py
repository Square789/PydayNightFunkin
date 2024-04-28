#!/usr/bin/env python3

import argparse


def main():
	argparser = argparse.ArgumentParser()
	argparser.add_argument(
		"--less-debug",
		"-l",
		action = "count",
		default = 0,
		help = (
			"Lowers PNF's debug level. If this flag isn't specified, will launch in debug mode "
			"and with the debug pane active. If specified once, will disable the debug pane. "
			"If specified more often than that, will disable debug mode and the debug pane."
		),
	)

	# You really want to keep this defaulting to `True` unless you haven't
	# touched the rendering backend AND not seen an OpenGL error for at
	# least 20 hours on at least three different systems.
	# This bool enables/disables pyglet's GL error checking, causing PNF
	# to silently drown in errors should something go wrong if this is
	# `False`. As it does run some python code each GL call (of which there's
	# dozens per frame), it should give some speedup when disabled however.
	argparser.add_argument(
		"--no-gl-errcheck",
		"-g",
		action = "store_false",
		help = (
			"Disables pyglet's OpenGL error checking, speeding up rendering calls.\n"
			"However, if something goes wrong while rendering, no one will ever know."
		),
	)

	argparser.add_argument(
		"--vsync",
		"-v",
		action = "store_true",
		help = (
			"Enables vsync. This may remove screentearing at the potential cost of "
			"dropping frames, or do absolutely nothing. Highly dependant on the intricacies "
			"of your system."
		),
	)

	result = argparser.parse_args()

	import pyglet
	pyglet.options["debug_gl"] = result.no_gl_errcheck

	from pyday_night_funkin.main_game import Game
	Game(2 - result.less_debug, result.vsync).run()


if __name__ == "__main__":
	main()
