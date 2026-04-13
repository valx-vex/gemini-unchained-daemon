#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage: fleet_sync.sh [--target-dir PATH] [--no-delete] [--skip-bootstrap] host [host ...]

Sync this Gemini Unchained checkout to remote nodes, refresh the ~/bin launchers,
and optionally bootstrap the daemon locally on each remote node.
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
DELETE_MODE=1
BOOTSTRAP_MODE=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target-dir)
      [ "$#" -ge 2 ] || { usage >&2; exit 1; }
      TARGET_DIR="$2"
      shift 2
      ;;
    --no-delete)
      DELETE_MODE=0
      shift
      ;;
    --skip-bootstrap)
      BOOTSTRAP_MODE=0
      shift
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

RSYNC_DELETE_FLAG=""
if [ "$DELETE_MODE" -eq 1 ]; then
  RSYNC_DELETE_FLAG="--delete"
fi

for HOST in "$@"; do
  printf '==> Syncing %s\n' "$HOST"
  rsync -az $RSYNC_DELETE_FLAG \
    --exclude '.DS_Store' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude 'node_modules' \
    "$PROJECT_ROOT/" \
    "$HOST:$TARGET_DIR/"

  ssh "$HOST" "mkdir -p \"\$HOME/bin\" && \
    ln -sfn \"$TARGET_DIR/bin/gemini-unchained-daemon\" \"\$HOME/bin/gemini-unchained-daemon\" && \
    ln -sfn \"$TARGET_DIR/bin/hal-deploy-gemini-daemon\" \"\$HOME/bin/hal-deploy-gemini-daemon\""

  if [ "$BOOTSTRAP_MODE" -eq 1 ]; then
    ssh "$HOST" "set -eu; export PATH=\"\$HOME/bin:\$PATH\"; command -v gemini >/dev/null 2>&1; /bin/sh \"$TARGET_DIR/scripts/bootstrap_runtime.sh\""
  fi
done
