"""Set the project version in the pyproject.toml file."""

import sys
from pathlib import Path

import tomli
import tomli_w

with Path("pyproject.toml").open(mode="rb") as f:
    pyproject = tomli.load(f)

print(f"set version to {sys.argv[1]}")

pyproject["project"]["version"] = sys.argv[1]

with Path("pyproject.toml").open("wb") as f:
    tomli_w.dump(pyproject, f)
