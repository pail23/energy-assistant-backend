"""Set the project version in the pyproject.toml file."""

import sys
from pathlib import Path

import tomli
import tomli_w

if len(sys.argv) == 2:
    with Path("pyproject.toml").open(mode="rb") as f:
        pyproject = tomli.load(f)

    print(f"set version to {sys.argv[1]}")

    pyproject["project"]["version"] = sys.argv[1]

    with Path("pyproject.toml").open("wb") as f:
        tomli_w.dump(pyproject, f)
else:
    print("Error: setversion requires exactly one argument containing the version to be set.")
