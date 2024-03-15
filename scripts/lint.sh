#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

ruff check . --fix
black .
mypy energy_assistant --ignore-missing-imports
codespell
