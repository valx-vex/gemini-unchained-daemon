#!/bin/sh
set -eu

SCRIPT_PATH="$0"
while [ -L "$SCRIPT_PATH" ]; do
  LINK_TARGET="$(readlink "$SCRIPT_PATH")"
  case "$LINK_TARGET" in
    /*) SCRIPT_PATH="$LINK_TARGET" ;;
    *) SCRIPT_PATH="$(dirname "$SCRIPT_PATH")/$LINK_TARGET" ;;
  esac
done

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname "$SCRIPT_PATH")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m pip install --user -e "$PROJECT_ROOT"

USER_BASE="$("$PYTHON_BIN" -m site --user-base)"
printf 'Installed Gemini Unchained in editable mode.\n'
printf 'User scripts are usually placed in: %s/bin\n' "$USER_BASE"
printf 'Run: gemini-unchained-daemon doctor\n'
