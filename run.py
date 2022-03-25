#!/usr/bin/env python

import cProfile
import sys

from pyday_night_funkin.main_game import Game

if __name__ == "__main__":
	if "-p" in sys.argv:
		cProfile.run("Game().run()", filename = "_profile_stats")
	else:
		Game().run()
