from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from gemini_unchained_daemon.bootstrap import ensure_bootstrapped
from gemini_unchained_daemon.paths import (
    CONTROL_DIR,
    DAEMON_PID_FILE,
    DAEMON_STATE_FILE,
    GLOBAL_STOP_FILE,
    LOGS_DIR,
    PROJECT_ROOT,
    task_state_dir,
)
from gemini_unchained_daemon.runner import load_tasks
from gemini_unchained_daemon.swarm import update_task_status
from gemini_unchained_daemon.util import atomic_write_json, ensure_dir, load_json, utc_now


STOP_DAEMON = False


def _signal_handler(signum: int, _frame: Any) -> None:
    global STOP_DAEMON
    STOP_DAEMON = True


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


def _normalize_state(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        tasks = {}
    return {
        "version": int(payload.get("version", 1)),
        "updated_at": payload.get("updated_at", utc_now()),
        "daemon_pid": payload.get("daemon_pid", 0),
        "tasks": tasks,
    }


def _save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(DAEMON_STATE_FILE, state)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _reap_child_if_exited(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        waited_pid, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return False
    return waited_pid == pid


def _read_worker_payload(worker_state_file: Path) -> dict[str, Any]:
    payload = load_json(worker_state_file, {})
    return payload if isinstance(payload, dict) else {}


def reconcile_running(state: dict[str, Any], tasks_file: Path | None = None) -> None:
    now = utc_now()
    for task_id, entry in state["tasks"].items():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status", "")).lower() != "running":
            continue
        pid = int(entry.get("pid", 0))
        if not _reap_child_if_exited(pid) and _pid_alive(pid):
            entry["last_seen_at"] = now
            continue
        worker_state_file = Path(str(entry.get("worker_state_file", "")))
        worker_payload = _read_worker_payload(worker_state_file)
        worker_status = str(worker_payload.get("status", "")).strip().lower()
        entry["status"] = worker_status or "exited"
        entry["ended_at"] = now
        entry["last_seen_at"] = now
        if tasks_file is not None and worker_status:
            update_task_status(
                tasks_file,
                task_id,
                worker_status,
                completion_reason=str(worker_payload.get("completion_reason", "")).strip(),
                last_error=str(worker_payload.get("last_error", "")).strip(),
            )


def count_running(state: dict[str, Any]) -> int:
    return sum(1 for entry in state["tasks"].values() if isinstance(entry, dict) and entry.get("status") == "running")


def should_spawn(task_id: str, state_entry: dict[str, Any] | None) -> bool:
    if not state_entry:
        return True
    return str(state_entry.get("status", "")).lower() not in {"running", "completed", "failed", "paused", "exited"}


def spawn_task(task_id: str, tasks_file: Path, state: dict[str, Any]) -> None:
    task_log_dir = ensure_dir(LOGS_DIR / "daemon")
    log_file = task_log_dir / f"{task_id}.log"
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(PROJECT_ROOT / "src")
    command = [
        sys.executable,
        "-m",
        "gemini_unchained_daemon",
        "run-task",
        "--task-id",
        task_id,
        "--tasks-file",
        str(tasks_file),
    ]
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"\n=== SPAWN {utc_now()} ===\n")
        handle.write("CMD: " + " ".join(command) + "\n")
        handle.flush()
        proc = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    state["tasks"][task_id] = {
        "status": "running",
        "pid": proc.pid,
        "spawned_at": utc_now(),
        "last_seen_at": utc_now(),
        "log_file": str(log_file),
        "worker_state_file": str(task_state_dir(task_id) / "current_run.json"),
    }


def dispatch_once(*, tasks_file: Path, max_workers: int) -> dict[str, Any]:
    ensure_bootstrapped()
    state = _normalize_state(load_json(DAEMON_STATE_FILE, {}))
    existing_daemon_pid = int(state.get("daemon_pid", 0))
    if existing_daemon_pid > 0 and not _pid_alive(existing_daemon_pid):
        state["daemon_pid"] = 0
    reconcile_running(state, tasks_file)
    available_slots = max(0, max_workers - count_running(state))
    if not GLOBAL_STOP_FILE.exists():
        for task in load_tasks(tasks_file):
            if available_slots <= 0:
                break
            entry = state["tasks"].get(task.id)
            if not should_spawn(task.id, entry):
                continue
            if task.status != "pending":
                continue
            spawn_task(task.id, tasks_file, state)
            available_slots -= 1
    _save_state(state)
    return state


def run_watch(*, tasks_file: Path, interval: int, max_workers: int) -> int:
    ensure_bootstrapped()
    ensure_dir(CONTROL_DIR)
    DAEMON_PID_FILE.write_text(f"{os.getpid()}\n", encoding="utf-8")
    try:
        while not STOP_DAEMON and not GLOBAL_STOP_FILE.exists():
            state = _normalize_state(load_json(DAEMON_STATE_FILE, {}))
            state["daemon_pid"] = os.getpid()
            _save_state(state)
            dispatch_once(tasks_file=tasks_file, max_workers=max_workers)
            time.sleep(interval)
        return 0
    finally:
        if DAEMON_PID_FILE.exists():
            DAEMON_PID_FILE.unlink()
