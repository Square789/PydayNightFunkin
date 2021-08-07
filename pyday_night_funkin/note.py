
import typing as t
from enum import IntEnum

from pyday_night_funkin.pnf_sprite import PNFSprite


class NOTE_TYPE(IntEnum):
	LEFT = 0
	DOWN = 1
	UP = 2
	RIGHT = 3
	

class Note():
	def __init__(self, time: float, type_: NOTE_TYPE, sustain: float) -> None:
		self.time = time
		self.type_ = type_
		self.sustain = sustain

	def create_sprite(self) -> PNFSprite:
		pass

