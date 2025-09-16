#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
VENV="$ROOT/.venv312/bin/python"
SETTINGS="$ROOT/.vscode/settings.json"

if [ ! -f "$VENV" ]; then
  echo "Virtualenv python not found at $VENV"
  echo "Please create .venv312 and install dependencies: python -m venv .venv312 && .venv312/bin/python -m pip install -r requirements.txt"
  exit 1
fi

echo "Ensuring VS Code settings point to .venv312"
jq --arg p "${VENV}" '."python.defaultInterpreterPath" = $p' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
echo "Updated $SETTINGS to use $VENV"
echo "Please reload VS Code window (Cmd+Shift+P -> Developer: Reload Window) to apply settings."
