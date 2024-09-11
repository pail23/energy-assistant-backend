import sys

import tomli
import tomli_w

with open("pyproject.toml", "rb") as f:
    pyproject = tomli.load(f)

print(f"set version to {sys.argv[1]}")

pyproject["project"]["version"] = sys.argv[1]

with open("pyproject.toml", "wb") as f:
    tomli_w.dump(pyproject, f)
