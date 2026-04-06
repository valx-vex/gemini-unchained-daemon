from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "templates"
DEFAULT_MODEL = "gemini-3-pro-preview"
USER_HOME = Path.home()

LIVE_GEMINI_HOME = USER_HOME / ".gemini"
DAEMON_ROOT = USER_HOME / ".hal-gemini-daemon"
DAEMON_GEMINI_HOME = DAEMON_ROOT / ".gemini"

RUNTIME_ROOT = DAEMON_ROOT / "runtime"
TASKS_DIR = RUNTIME_ROOT / "tasks"
STATE_DIR = RUNTIME_ROOT / "state"
LOGS_DIR = RUNTIME_ROOT / "logs"
CONTEXT_DIR = RUNTIME_ROOT / "context"
LOCKS_DIR = RUNTIME_ROOT / "locks"
CONTROL_DIR = RUNTIME_ROOT / "control"
HIVE_MIND_FILE = RUNTIME_ROOT / "HIVE_MIND.md"

DEFAULT_TASKS_FILE = TASKS_DIR / "TASKS.json"
DAEMON_STATE_FILE = STATE_DIR / "daemon_state.json"
DAEMON_PID_FILE = LOCKS_DIR / "daemon.pid"
GLOBAL_STOP_FILE = CONTROL_DIR / "global.stop"


def task_state_dir(task_id: str) -> Path:
    return STATE_DIR / task_id


def task_logs_dir(task_id: str) -> Path:
    return LOGS_DIR / task_id


def task_context_dir(task_id: str) -> Path:
    return CONTEXT_DIR / task_id
