#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

echo "Ruff format..."
ruff format .
echo "Ruff check..."
ruff check . --fix
echo "mypy..."
mypy energy_assistant --ignore-missing-imports
echo "codespell..."
codespell
