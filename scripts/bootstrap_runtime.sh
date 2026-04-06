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
QUEUE_FILE="${HOME}/.hal-gemini-daemon/runtime/tasks/TASKS.json"

gemini-unchained-daemon doctor

if [ ! -f "$QUEUE_FILE" ] || ! grep -q '"id"' "$QUEUE_FILE"; then
  mkdir -p "$(dirname "$QUEUE_FILE")"
  cp "$PROJECT_ROOT/TASKS.example.json" "$QUEUE_FILE"
  printf 'Seeded example queue at %s\n' "$QUEUE_FILE"
else
  printf 'Queue already contains tasks: %s\n' "$QUEUE_FILE"
fi

printf 'Runtime ready at %s\n' "${HOME}/.hal-gemini-daemon"
