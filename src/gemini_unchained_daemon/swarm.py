from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Any, Callable

from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon.paths import DEFAULT_TASKS_FILE, HIVE_MIND_FILE
from gemini_unchained_daemon.util import atomic_write_json, atomic_write_text, compact_whitespace, ensure_dir, load_json, slugify, utc_now


def ensure_hive_mind(hive_mind_file: Path = HIVE_MIND_FILE) -> Path:
    ensure_dir(hive_mind_file.parent)
    if not hive_mind_file.exists():
        atomic_write_text(
            hive_mind_file,
            "# HIVE MIND\n\nShared swarm memory for Gemini Unchained workers.\n",
        )
    return hive_mind_file


def read_hive_mind_excerpt(max_lines: int = 10, hive_mind_file: Path = HIVE_MIND_FILE) -> str:
    ensure_hive_mind(hive_mind_file)
    lines = [line.rstrip() for line in hive_mind_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    tail = lines[-max_lines:]
    return "\n".join(tail) if tail else "No hive memory yet."


def append_hive_summary(task: TaskSpec, state: dict[str, Any], hive_mind_file: Path = HIVE_MIND_FILE) -> str:
    ensure_hive_mind(hive_mind_file)
    rounds = state.get("rounds", []) if isinstance(state.get("rounds"), list) else []
    last_round = rounds[-1] if rounds else {}
    final_text = compact_whitespace(str(last_round.get("assistant_text", "")))
    status_line = compact_whitespace(str(last_round.get("status_line", ""))) or "No STATUS line was recorded."
    spawned_task_ids = state.get("spawned_task_ids", []) if isinstance(state.get("spawned_task_ids"), list) else []

    line_one = f"Task `{task.id}` completed after {max(1, len(rounds))} round(s) while working on: {compact_whitespace(task.goal)[:220]}."
    line_two = f"Key finding: {(final_text or 'No assistant text was captured.')[:280]}."
    if spawned_task_ids:
        carry_forward = "Generated follow-on tasks: " + ", ".join(str(task_id) for task_id in spawned_task_ids[:8])
    else:
        carry_forward = status_line
    line_three = f"Carry forward: {carry_forward[:280]}."
    entry = "\n".join(
        [
            f"## {utc_now()}",
            line_one,
            line_two,
            line_three,
        ]
    )
    with hive_mind_file.open("a", encoding="utf-8") as handle:
        handle.write("\n" + entry + "\n")
    return entry


def _extract_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    start_index: int | None = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if start_index is None:
            if char == "{":
                start_index = index
                depth = 1
                in_string = False
                escape = False
            continue

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                objects.append(text[start_index:index + 1])
                start_index = None

    return objects


def extract_new_task_payloads(text: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in _extract_json_objects(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict) or "NEW_TASK" not in parsed:
            continue
        new_task_value = parsed["NEW_TASK"]
        task_items = [new_task_value] if isinstance(new_task_value, dict) else new_task_value if isinstance(new_task_value, list) else []
        for item in task_items:
            if not isinstance(item, dict):
                continue
            serialized = json.dumps(item, sort_keys=True, ensure_ascii=True)
            if serialized in seen:
                continue
            seen.add(serialized)
            payloads.append(item)
    return payloads


def _lock_path(tasks_file: Path) -> Path:
    return tasks_file.with_suffix(tasks_file.suffix + ".lock")


def _with_task_queue_lock(tasks_file: Path, mutator: Callable[[dict[str, Any]], Any]) -> Any:
    ensure_dir(tasks_file.parent)
    lock_path = _lock_path(tasks_file)
    ensure_dir(lock_path.parent)
    with lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        payload = load_json(tasks_file, {"tasks": []})
        if not isinstance(payload, dict):
            payload = {"tasks": []}
        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            tasks = []
        payload["tasks"] = tasks
        result = mutator(payload)
        atomic_write_json(tasks_file, payload)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        return result


def update_task_status(tasks_file: Path, task_id: str, status: str, **extra_fields: Any) -> bool:
    def mutate(payload: dict[str, Any]) -> bool:
        for task in payload["tasks"]:
            if isinstance(task, dict) and str(task.get("id", "")).strip() == task_id:
                task["status"] = status
                task["updated_at"] = utc_now()
                for key, value in extra_fields.items():
                    task[key] = value
                return True
        return False

    return bool(_with_task_queue_lock(tasks_file, mutate))


def _task_signature(payload: dict[str, Any]) -> tuple[str, str, str]:
    return (
        compact_whitespace(str(payload.get("goal", ""))).lower(),
        compact_whitespace(str(payload.get("task_type", ""))).lower(),
        compact_whitespace(str(payload.get("workdir", ""))),
    )


def _unique_task_id(base: str, existing_ids: set[str]) -> str:
    candidate = base or "task"
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    existing_ids.add(candidate)
    return candidate


def _build_spawned_task(parent_task: TaskSpec, payload: dict[str, Any], existing_ids: set[str]) -> dict[str, Any] | None:
    goal = compact_whitespace(str(payload.get("goal", "")))
    if not goal:
        return None

    task_type = compact_whitespace(str(payload.get("task_type", "subtask"))) or "subtask"
    base_id = compact_whitespace(str(payload.get("id", ""))) or slugify(f"{parent_task.id}-{task_type}-{goal}", 56)
    child_task = parent_task.to_dict()
    child_task.update(
        {
            "id": _unique_task_id(base_id, existing_ids),
            "status": "pending",
            "goal": goal,
            "task_type": task_type,
            "parent_task_id": parent_task.id,
            "spawned_by": parent_task.id,
            "spawned_at": utc_now(),
        }
    )
    for key in (
        "success_criteria",
        "rounds",
        "workdir",
        "include_files",
        "timeout",
        "beacon_interval",
        "mcp_mode",
        "retry_max",
        "retry_backoff",
        "no_preamble",
        "quiet",
        "model",
        "completion_marker",
    ):
        if key in payload:
            child_task[key] = payload[key]
    return child_task


def register_generated_tasks(
    tasks_file: Path,
    parent_task: TaskSpec,
    assistant_text: str,
) -> list[dict[str, Any]]:
    extracted = extract_new_task_payloads(assistant_text)
    if not extracted:
        return []

    def mutate(payload: dict[str, Any]) -> list[dict[str, Any]]:
        existing_ids = {
            str(task.get("id", "")).strip()
            for task in payload["tasks"]
            if isinstance(task, dict) and str(task.get("id", "")).strip()
        }
        existing_signatures = {
            _task_signature(task)
            for task in payload["tasks"]
            if isinstance(task, dict)
        }
        added: list[dict[str, Any]] = []
        for item in extracted:
            child_task = _build_spawned_task(parent_task, item, existing_ids)
            if not child_task:
                continue
            signature = _task_signature(child_task)
            if signature in existing_signatures:
                continue
            payload["tasks"].append(child_task)
            existing_signatures.add(signature)
            added.append(child_task)
        return added

    return list(_with_task_queue_lock(tasks_file, mutate))


__all__ = [
    "append_hive_summary",
    "ensure_hive_mind",
    "extract_new_task_payloads",
    "read_hive_mind_excerpt",
    "register_generated_tasks",
    "update_task_status",
]
