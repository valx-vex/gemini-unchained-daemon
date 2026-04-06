from __future__ import annotations

import argparse
import os
import signal
from pathlib import Path

from gemini_unchained_daemon.bootstrap import bootstrap, reseed_auth
from gemini_unchained_daemon.daemon import DAEMON_PID_FILE, dispatch_once, run_watch
from gemini_unchained_daemon.doctor import run_doctor
from gemini_unchained_daemon.paths import CONTROL_DIR, DAEMON_STATE_FILE, DEFAULT_TASKS_FILE, GLOBAL_STOP_FILE
from gemini_unchained_daemon.runner import load_task, run_task
from gemini_unchained_daemon.util import ensure_dir, load_json


def _tasks_file(value: str | None) -> Path:
    return Path(value).expanduser() if value else DEFAULT_TASKS_FILE


def cmd_watch(args: argparse.Namespace) -> int:
    bootstrap()
    if GLOBAL_STOP_FILE.exists():
        GLOBAL_STOP_FILE.unlink()
    return run_watch(tasks_file=_tasks_file(args.tasks_file), interval=args.interval, max_workers=args.max_workers)


def cmd_once(args: argparse.Namespace) -> int:
    bootstrap()
    dispatch_once(tasks_file=_tasks_file(args.tasks_file), max_workers=args.max_workers)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    state = load_json(DAEMON_STATE_FILE, {})
    tasks = state.get("tasks", {}) if isinstance(state, dict) else {}
    daemon_pid = state.get("daemon_pid", 0) if isinstance(state, dict) else 0
    print(f"daemon_pid={daemon_pid}")
    if not tasks:
        print("No tracked tasks.")
        return 0
    for task_id, entry in sorted(tasks.items()):
        status = entry.get("status", "unknown")
        pid = entry.get("pid", 0)
        print(f"{task_id}: status={status} pid={pid}")
    return 0


def cmd_stop(_args: argparse.Namespace) -> int:
    ensure_dir(CONTROL_DIR)
    GLOBAL_STOP_FILE.write_text("stop\n", encoding="utf-8")
    if DAEMON_PID_FILE.exists():
        pid_text = DAEMON_PID_FILE.read_text(encoding="utf-8").strip()
        if pid_text.isdigit():
            try:
                os.kill(int(pid_text), signal.SIGTERM)
            except (PermissionError, ProcessLookupError):
                pass
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    exit_code, checks = run_doctor()
    for check in checks:
        print(f"{check['status'].upper():4} {check['name']}: {check['detail']}")
    return exit_code


def cmd_reseed_auth(_args: argparse.Namespace) -> int:
    report = reseed_auth()
    print("Copied:", ", ".join(report.copied_files) or "none")
    if report.missing_files:
        print("Missing:", ", ".join(report.missing_files))
    return 0


def cmd_run_task(args: argparse.Namespace) -> int:
    tasks_file = _tasks_file(args.tasks_file)
    task = load_task(tasks_file, args.task_id)
    state = run_task(task, tasks_file=tasks_file)
    print(state["status"])
    return 0 if state["status"] == "completed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gemini-unchained-daemon")
    subparsers = parser.add_subparsers(dest="command")

    watch = subparsers.add_parser("watch")
    watch.add_argument("--tasks-file")
    watch.add_argument("--interval", type=int, default=15)
    watch.add_argument("--max-workers", type=int, default=3)
    watch.set_defaults(func=cmd_watch)

    once = subparsers.add_parser("once")
    once.add_argument("--tasks-file")
    once.add_argument("--max-workers", type=int, default=3)
    once.set_defaults(func=cmd_once)

    status = subparsers.add_parser("status")
    status.set_defaults(func=cmd_status)

    stop = subparsers.add_parser("stop")
    stop.set_defaults(func=cmd_stop)

    doctor = subparsers.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)

    reseed = subparsers.add_parser("reseed-auth")
    reseed.set_defaults(func=cmd_reseed_auth)

    run_task_parser = subparsers.add_parser("run-task")
    run_task_parser.add_argument("--task-id", required=True)
    run_task_parser.add_argument("--tasks-file")
    run_task_parser.set_defaults(func=cmd_run_task)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args(["watch"])
    return args.func(args)
