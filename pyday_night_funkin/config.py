
from dataclasses import dataclass
import typing as t


@dataclass
class Config():
	scroll_speed: float

	@staticmethod
	def validate(cfg: t.Dict) -> bool:
		return True # TODO: ye
