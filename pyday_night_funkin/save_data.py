
import json
import os
from pathlib import Path
import platform
import typing as t

from loguru import logger
from pyglet.window import key
from schema import Or, Schema

from pyday_night_funkin.enums import CONTROL


class UnsupportedPlatformError(Exception):
	pass


CONFIG = "config.json"
HIGHSCORES = "highscores.json"


class Config:
	"""
	Stores game configuration. Some of these options make gameplay
	easier or harder.

	`scroll_speed`: A multiplier applied to every song's scroll
		speed.
	`safe_window`: Amount of time notes can be hit before/after their
		actual time and still count as a hit, in ms.
	`key_bindings`: Key bindings mapping each control input in `CONTROL`
		to its corresponding keys (in a list) in pyglet's `key` module.
	"""

	SCHEMA = Schema(
		{
			"scroll_speed": float,
			"safe_window": float,
			"key_bindings": {
				str: [str],
			},
		},
		ignore_extra_keys = True,
	)

	def __init__(
		self,
		scroll_speed: float,
		safe_window: float,
		key_bindings: t.Dict[CONTROL, t.Sequence[int]],
	) -> None:
		self.scroll_speed = scroll_speed
		self.safe_window = safe_window
		self.key_bindings = key_bindings

	@classmethod
	def from_dict(cls, data: t.Dict):
		"""
		Creates config from a json dict, probably read out of a
		saved file.

		:raises SchemaError: When the schema library fails validating
		the dict.
		:raises AttributeError: On failure converting the saved
		bindings back to their enum members.
		"""
		data = cls.SCHEMA.validate(data)

		return cls(
			data["scroll_speed"],
			data["safe_window"],
			{
				getattr(CONTROL, ctrl_name): [getattr(key, k) for k in key_names]
				for ctrl_name, key_names in data["key_bindings"].items()
			},
		)

	def to_dict(self) -> t.Dict:
		"""
		Converts a Config object to a dict that is readable by
		`Config.from_dict` and can be written to disk with the
		json module.
		"""

		return {
			"scroll_speed": self.scroll_speed,
			"safe_window": self.safe_window,
			"key_bindings": {
				ctrl.name: [key.symbol_string(vv) for vv in v]
				for ctrl, v in self.key_bindings.items()
			},
		}

	@classmethod
	def get_default(cls):
		return cls(
			scroll_speed = 1.0,
			safe_window = 167.0,
			key_bindings = {
				CONTROL.LEFT: [key.LEFT, key.A],
				CONTROL.DOWN: [key.DOWN, key.S],
				CONTROL.UP: [key.UP, key.W],
				CONTROL.RIGHT: [key.RIGHT, key.D],
				CONTROL.ENTER: [key.ENTER],
				CONTROL.BACK: [key.BACKSPACE],
				CONTROL.DEBUG_DESYNC: [key._1],
				CONTROL.DEBUG_WIN: [key._2],
				CONTROL.DEBUG_LOSE: [key._3],
			},
		)


class SaveData:
	"""
	Save data holder class. Contains the config as a Config object and
	highscores as a simple string -> int dict.
	Effectively these two files are subdivided by the criteria
	"modification == cheating"
	"""

	HIGHSCORE_SCHEMA = Schema(Or({str: int}, {}))

	def __init__(self, config: Config, highscores: t.Dict[str, int]) -> None:
		self.config = config
		self.highscores = highscores
		self._save_data_location = self.get_savedata_location()

	@classmethod
	def load(cls):
		"""
		Loads savedata from disk.
		"""
		location = cls.get_savedata_location()
		if (cfg_path := location / CONFIG).exists():
			with cfg_path.open("r") as f:
				cfg = Config.from_dict(json.load(f))
		else:
			logger.info("Config file does not exist, creating default.")
			cfg = Config.get_default()

		if (highscore_path := location / HIGHSCORES).exists():
			with highscore_path.open("r") as f:
				hs = cls.HIGHSCORE_SCHEMA.validate(json.load(f))
		else:
			logger.info("Highscore file does not exist, creating empty.")
			hs = {}

		return cls(cfg, hs)

	def save(self) -> None:
		"""
		Saves the savedata to disk.
		Will attempt to create the save directory as well.

		:raises OSError: on any file system-related failure when
		creating directories, checking for their existence, or
		opening, writing and closing the save data files.
		"""
		# Not using os.makedirs here as the creation mode isn't applied to
		# all the directories. It's likely only one dir will be created at
		# most anyways, but they don't call me Oliver the Overengineer for
		# nothing.
		creation_start_path = self._save_data_location
		leaves: t.List[str] = []
		while not creation_start_path.exists():
			leaves.append(creation_start_path.name)
			creation_start_path = creation_start_path.parent
		to_create = creation_start_path
		for name in reversed(leaves):
			to_create = to_create / name
			to_create.mkdir(0o775)

		with (self._save_data_location / CONFIG).open("w") as f:
			json.dump(self.config.to_dict(), f)

		with (self._save_data_location / HIGHSCORES).open("w") as f:
			json.dump(self.highscores, f)

	@staticmethod
	def get_savedata_location() -> Path:
		""""
		Returns the platform-dependant save data directory, or raises an
		`UnsupportedPlatformError` if this is running on a smart fridge
		or other obscure environments.
		"""
		if platform.system() == "Windows":
			return Path(os.environ["APPDATA"]) / "PydayNightFunkin"

		elif platform.system() == "Linux":
			target = Path("~").expanduser()
			if "XDG_DATA_HOME" in os.environ:
				target = Path(os.environ["XDG_DATA_HOME"])
			return target / ".local" / "share" / "PydayNightFunkin"

		elif platform.system() == "Darwin":
			target = Path("~").expanduser()
			return target / "Library" / "Application Support" / "PydayNightFunkin"

		else:
			raise UnsupportedPlatformError(f"Unknown platform: {platform.system()!r}")
