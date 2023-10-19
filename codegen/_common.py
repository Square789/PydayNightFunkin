import argparse
import os
from pathlib import Path
import sys
import typing as t

from dotenv import load_dotenv
load_dotenv()


def _convert_bool_env_var(v: t.Optional[str]) -> bool:
	if v == "0":
		return False
	return bool(v)


def cwd_sanity_check(location: t.Union[str, Path]) -> None:
	cwd = Path.cwd()
	if not all(p.exists() for p in ((cwd / location), (cwd / "LICENSE"))):
		raise RuntimeError("Codegen script is being ran from bad location")


# Pretty garbage function to have args override the env
def get_options(*args):
	_env = {name: default for name, _, default in args}

	for name, type_, _ in args:
		env_name = "PNF_" + name.upper().replace("-", "_")
		if (r := os.getenv(env_name)) is None:
			continue

		if type_ is bool:
			_env[name] = _convert_bool_env_var(r)
		else:
			_env[name] = r

	p = argparse.ArgumentParser()
	for name, type_, default in args:
		if type_ is bool:
			action = "store_true"
		else:
			action = "store"
		p.add_argument("--" + name, action=action, default=argparse.SUPPRESS, dest=name)

	apns = p.parse_args(sys.argv[1:])
	for name in _env:
		if hasattr(apns, name):
			_env[name] = getattr(apns, name)

	return tuple(_env[name] for name, *_ in args)
