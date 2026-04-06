from __future__ import annotations

import os
import re
import signal
import subprocess
import time
import json
from pathlib import Path
from typing import Any

from gemini_unchained_daemon.bootstrap import ensure_bootstrapped
from gemini_unchained_daemon.gemini_json import ParsedCliOutput, parse_cli_output
from gemini_unchained_daemon.mcp import emit_allowed_mcp_args
from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon.paths import (
    CONTROL_DIR,
    DAEMON_GEMINI_HOME,
    DAEMON_ROOT,
    DEFAULT_TASKS_FILE,
    GLOBAL_STOP_FILE,
    LOCKS_DIR,
    task_context_dir,
    task_logs_dir,
    task_state_dir,
)
from gemini_unchained_daemon.prompting import build_round_prompt, derive_rolling_context, load_persona
from gemini_unchained_daemon.swarm import append_hive_summary, read_hive_mind_excerpt, register_generated_tasks, update_task_status
from gemini_unchained_daemon.util import atomic_write_json, atomic_write_text, ensure_dir, slugify, utc_now


CAPACITY_PATTERN = re.compile(r"MODEL_CAPACITY_EXHAUSTED|RESOURCE_EXHAUSTED|429|rateLimitExceeded", re.IGNORECASE)
STATUS_PATTERN = re.compile(r"^STATUS:\s*(.+)$", re.MULTILINE)
BLOCKED_PATTERN = re.compile(r"\[TASK_BLOCKED:\s*(.+?)\]", re.IGNORECASE | re.DOTALL)
ERROR_PATTERN = re.compile(r"\[TASK_ERROR:\s*(.+?)\]", re.IGNORECASE | re.DOTALL)

CURRENT_GEMINI_PROCESS: subprocess.Popen[str] | None = None
STOP_REQUESTED = False


def _signal_handler(signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    if CURRENT_GEMINI_PROCESS is not None and CURRENT_GEMINI_PROCESS.poll() is None:
        CURRENT_GEMINI_PROCESS.terminate()


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


def _task_stop_file(task_id: str) -> Path:
    return CONTROL_DIR / f"{task_id}.stop"


def stop_requested(task_id: str) -> bool:
    return STOP_REQUESTED or GLOBAL_STOP_FILE.exists() or _task_stop_file(task_id).exists()


def _task_lock_path(task_id: str) -> Path:
    return LOCKS_DIR / f"{task_id}.lock"


def acquire_task_lock(task_id: str) -> Path:
    lock_path = _task_lock_path(task_id)
    ensure_dir(lock_path.parent)
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")
    return lock_path


def release_task_lock(lock_path: Path) -> None:
    if lock_path.exists():
        lock_path.unlink()


def load_tasks(tasks_file: Path) -> list[TaskSpec]:
    if not tasks_file.exists():
        payload = {}
    else:
        with tasks_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    return [TaskSpec.from_dict(task) for task in tasks if isinstance(task, dict)]


def load_task(tasks_file: Path, task_id: str) -> TaskSpec:
    for task in load_tasks(tasks_file):
        if task.id == task_id:
            return task
    raise ValueError(f"Task '{task_id}' not found in {tasks_file}")


def _match_success_criteria(pattern: str, assistant_text: str) -> bool:
    if not pattern:
        return False
    try:
        return re.search(pattern, assistant_text, re.MULTILINE) is not None
    except re.error:
        return pattern in assistant_text


def _invoke_gemini(
    *,
    prompt: str,
    task: TaskSpec,
    allowlist_args: list[str],
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    global CURRENT_GEMINI_PROCESS

    env = dict(os.environ)
    env["GEMINI_CLI_HOME"] = str(DAEMON_ROOT)
    command = [
        "gemini",
        "-p",
        "@",
        "--approval-mode=yolo",
        "--output-format",
        "json",
        "-m",
        task.model,
        *allowlist_args,
    ]
    started_at = utc_now()
    proc = subprocess.Popen(
        command,
        cwd=str(task.workdir_path),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    CURRENT_GEMINI_PROCESS = proc
    timed_out = False
    try:
        stdout, stderr = proc.communicate(prompt, timeout=task.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    finally:
        CURRENT_GEMINI_PROCESS = None

    completed_at = utc_now()
    atomic_write_text(stdout_path, stdout)
    atomic_write_text(stderr_path, stderr)
    combined = (stdout or "") + ("\n" + stderr if stderr else "")
    parsed = parse_cli_output(stdout or combined)
    return {
        "command": command,
        "started_at": started_at,
        "completed_at": completed_at,
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "combined_output": combined,
        "parsed": parsed,
    }


def _retry_reason(result: dict[str, Any]) -> str:
    if result["timed_out"]:
        return "timeout"
    if result["exit_code"] != 0:
        return f"exit_code_{result['exit_code']}"
    if not result["combined_output"].strip():
        return "empty_output"
    if CAPACITY_PATTERN.search(result["combined_output"]):
        return "capacity"
    return ""


def _status_line(assistant_text: str) -> str:
    match = STATUS_PATTERN.search(assistant_text)
    return f"STATUS: {match.group(1).strip()}" if match else ""


def _marker_payload(task: TaskSpec, assistant_text: str) -> dict[str, Any]:
    blocked = BLOCKED_PATTERN.search(assistant_text)
    error = ERROR_PATTERN.search(assistant_text)
    return {
        "completed": task.completion_marker in assistant_text or "ALEXKO_UNCHAINED_COMPLETE" in assistant_text,
        "blocked": blocked.group(1).strip() if blocked else "",
        "error": error.group(1).strip() if error else "",
    }


def _continuation_prompt(markers: dict[str, Any], success_matched: bool, assistant_text: str) -> str:
    if markers["completed"]:
        return "Task completed."
    if markers["blocked"]:
        return f"Task blocked: {markers['blocked']}"
    if markers["error"]:
        return f"Task error: {markers['error']}"
    if success_matched:
        return "Success criteria matched. Emit the completion marker now."
    excerpt = assistant_text[:240].strip() or "No assistant text extracted."
    return f"Continue from the current state. Latest model output excerpt: {excerpt}"


def _init_run_state(task: TaskSpec, run_id: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "run_id": run_id,
        "task": task.to_dict(),
        "status": "running",
        "created_at": now,
        "updated_at": now,
        "completion_reason": "",
        "goal_detected": False,
        "last_error": "",
        "spawned_task_ids": [],
        "hive_mind_entry": "",
        "rolling": {
            "cumulative_summary": "No prior rounds.",
            "previous_round_output": "No prior rounds.",
            "latest_pending_state": "No prior state.",
        },
        "rounds": [],
    }


def _save_run_state(task_id: str, state: dict[str, Any]) -> Path:
    state["updated_at"] = utc_now()
    state_path = task_state_dir(task_id) / "current_run.json"
    atomic_write_json(state_path, state)
    return state_path


def _finalize_task(task: TaskSpec, state: dict[str, Any], tasks_file: Path) -> dict[str, Any]:
    if state["status"] == "completed" and not state.get("hive_mind_entry"):
        state["hive_mind_entry"] = append_hive_summary(task, state)
    update_task_status(
        tasks_file,
        task.id,
        state["status"],
        completion_reason=state.get("completion_reason", ""),
        last_error=state.get("last_error", ""),
    )
    _save_run_state(task.id, state)
    return state


def run_task(task: TaskSpec, tasks_file: Path = DEFAULT_TASKS_FILE) -> dict[str, Any]:
    ensure_bootstrapped()
    if not task.id:
        raise ValueError("Task id is required")
    if not task.goal:
        raise ValueError("Task goal is required")

    lock_path = acquire_task_lock(task.id)
    run_id = f"{task.id}-{utc_now().replace(':', '').replace('-', '').lower()}-{slugify(task.goal, 24)}"
    state = _init_run_state(task, run_id)
    ensure_dir(task_state_dir(task.id))
    logs_dir = ensure_dir(task_logs_dir(task.id))
    context_dir = ensure_dir(task_context_dir(task.id))
    persona_text = load_persona(DAEMON_GEMINI_HOME / "GEMINI.md")
    hive_mind_excerpt = read_hive_mind_excerpt()
    allowlist_args = emit_allowed_mcp_args(task.mcp_mode)
    try:
        update_task_status(tasks_file, task.id, "running", started_at=utc_now())
        _save_run_state(task.id, state)
        for round_number in range(1, task.rounds + 1):
            if stop_requested(task.id):
                state["status"] = "paused"
                state["completion_reason"] = "stop_requested"
                break

            rolling_context = derive_rolling_context(state["rounds"])
            prompt = build_round_prompt(
                task=task,
                run_id=run_id,
                round_number=round_number,
                persona_text=persona_text,
                rolling_context=rolling_context,
                hive_mind_excerpt=hive_mind_excerpt if round_number == 1 else "",
            )
            prompt_path = context_dir / f"round_input_{round_number:03d}.md"
            atomic_write_text(prompt_path, prompt)

            attempts: list[dict[str, Any]] = []
            final_result: dict[str, Any] | None = None
            try:
                for attempt in range(1, task.retry_max + 2):
                    stdout_path = logs_dir / f"round_{round_number:03d}_attempt_{attempt:02d}.stdout.json"
                    stderr_path = logs_dir / f"round_{round_number:03d}_attempt_{attempt:02d}.stderr.log"
                    result = _invoke_gemini(
                        prompt=prompt,
                        task=task,
                        allowlist_args=allowlist_args,
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                    )
                    parsed: ParsedCliOutput = result["parsed"]
                    retry_reason = _retry_reason(result)
                    attempts.append(
                        {
                            "attempt": attempt,
                            "started_at": result["started_at"],
                            "completed_at": result["completed_at"],
                            "exit_code": result["exit_code"],
                            "timed_out": result["timed_out"],
                            "stdout_path": str(stdout_path),
                            "stderr_path": str(stderr_path),
                            "retry_reason": retry_reason,
                            "json_valid": parsed.json_valid,
                        }
                    )
                    final_result = result
                    if not retry_reason or attempt > task.retry_max:
                        break
                    time.sleep(task.retry_backoff[min(attempt - 1, len(task.retry_backoff) - 1)])
            except Exception as exc:
                state["status"] = "failed"
                state["completion_reason"] = "invocation_exception"
                state["last_error"] = str(exc)
                return _finalize_task(task, state, tasks_file)

            assert final_result is not None
            parsed = final_result["parsed"]
            assistant_text = parsed.assistant_text.strip()
            tool_summary = parsed.tool_summary.strip()
            markers = _marker_payload(task, assistant_text)
            success_matched = _match_success_criteria(task.success_criteria, assistant_text)
            generated_tasks = register_generated_tasks(tasks_file, task, assistant_text)
            round_entry = {
                "round": round_number,
                "started_at": attempts[0]["started_at"],
                "completed_at": attempts[-1]["completed_at"],
                "attempts": attempts,
                "assistant_text": assistant_text,
                "tool_summary": tool_summary,
                "status_line": _status_line(assistant_text),
                "markers": markers,
                "success_criteria_matched": success_matched,
                "continuation_prompt": _continuation_prompt(markers, success_matched, assistant_text),
                "generated_tasks": [generated_task["id"] for generated_task in generated_tasks],
            }
            state["rounds"].append(round_entry)
            state["spawned_task_ids"].extend(
                generated_task["id"]
                for generated_task in generated_tasks
                if generated_task["id"] not in state["spawned_task_ids"]
            )
            state["rolling"] = derive_rolling_context(state["rounds"])
            state["goal_detected"] = state["goal_detected"] or success_matched or markers["completed"]
            _save_run_state(task.id, state)

            if markers["completed"]:
                state["status"] = "completed"
                state["completion_reason"] = "completion_marker"
                break
            if markers["blocked"]:
                state["status"] = "paused"
                state["completion_reason"] = "task_blocked"
                state["last_error"] = markers["blocked"]
                break
            if markers["error"]:
                state["status"] = "failed"
                state["completion_reason"] = "task_error"
                state["last_error"] = markers["error"]
                break
            if stop_requested(task.id):
                state["status"] = "paused"
                state["completion_reason"] = "stop_requested"
                break
        else:
            if state["goal_detected"]:
                state["status"] = "completed"
                state["completion_reason"] = "max_rounds_success_criteria"
            else:
                state["status"] = "failed"
                state["completion_reason"] = "max_rounds_without_completion"

        return _finalize_task(task, state, tasks_file)
    finally:
        release_task_lock(lock_path)
