#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage: fleet_validate.sh [--target-dir PATH] [--wait-seconds N] [--model NAME] host [host ...]

Validate that Gemini Unchained is installed and responsive on each remote node.
EOF
}

SCRIPT_PATH="$0"
while [ -L "$SCRIPT_PATH" ]; do
  LINK_TARGET="$(readlink "$SCRIPT_PATH")"
  case "$LINK_TARGET" in
    /*) SCRIPT_PATH="$LINK_TARGET" ;;
    *) SCRIPT_PATH="$(dirname "$SCRIPT_PATH")/$LINK_TARGET" ;;
  esac
done

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname "$SCRIPT_PATH")/.." && pwd)"
TARGET_DIR="${TARGET_DIR:-$PROJECT_ROOT}"
WAIT_SECONDS="${WAIT_SECONDS:-90}"
MODEL="${MODEL:-auto}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target-dir)
      [ "$#" -ge 2 ] || { usage >&2; exit 1; }
      TARGET_DIR="$2"
      shift 2
      ;;
    --wait-seconds)
      [ "$#" -ge 2 ] || { usage >&2; exit 1; }
      WAIT_SECONDS="$2"
      shift 2
      ;;
    --model)
      [ "$#" -ge 2 ] || { usage >&2; exit 1; }
      MODEL="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

[ "$#" -gt 0 ] || { usage >&2; exit 1; }

for HOST in "$@"; do
  printf '==> Validating %s\n' "$HOST"
  ssh "$HOST" "set -eu
    export PATH=\"\$HOME/bin:\$PATH\"
    command -v gemini >/dev/null 2>&1
    test -x \"$TARGET_DIR/bin/gemini-unchained-daemon\"
    test -L \"\$HOME/bin/gemini-unchained-daemon\"
    test -L \"\$HOME/bin/hal-deploy-gemini-daemon\"
    test -f \"\$HOME/.hal-gemini-daemon/.gemini/settings.json\"
    test -f \"\$HOME/.hal-gemini-daemon/runtime/tasks/TASKS.json\"
    cd \"\$HOME/.hal-gemini-daemon\"
    export GEMINI_CLI_HOME=\"\$HOME/.hal-gemini-daemon\"
    OUTPUT=\$(printf 'Reply with exactly OK' | perl -e 'alarm shift; exec @ARGV' \"$WAIT_SECONDS\" gemini -p @ --approval-mode=yolo --output-format json --allowed-mcp-server-names __none__ -m \"$MODEL\" 2>&1 || true)
    printf '%s\n' \"\$OUTPUT\"
    printf '%s\n' \"\$OUTPUT\" | grep -Eq '\"response\"[[:space:]]*:[[:space:]]*\"OK\"|^[[:space:]]*OK[[:space:]]*$'
  "
done
