
import pyglet

from loguru import logger

if pyglet.version != "2.0.dev13":
	logger.warning("TL patches may fail!")

from pyday_night_funkin.core.pyglet_tl_patch.tl_label import TLLabel
from pyday_night_funkin.core.pyglet_tl_patch.tl_shapes import TLRectangle

__all__ = ["TLLabel", "TLRectangle"]
