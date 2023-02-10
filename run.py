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
	argparser.add_argument(
		"--no-gl-errcheck",
		"-g",
		action = "store_false",
		help = (
			"Disables pyglet's OpenGL error checking, speeding up rendering calls.\n"
			"However, if something goes wrong while rendering, no one will ever know."
		),
	)
	result = argparser.parse_args()

	import pyglet
	pyglet.options["debug_gl"] = result.no_gl_errcheck

	from pyday_night_funkin.main_game import Game
	Game(2 - result.less_debug).run()


if __name__ == "__main__":
	main()
