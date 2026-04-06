from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gemini_unchained_daemon.paths import DEFAULT_MODEL, PROJECT_ROOT


@dataclass(frozen=True)
class TaskSpec:
    id: str
    status: str
    goal: str
    task_type: str = "custom"
    success_criteria: str = ""
    rounds: int = 10
    workdir: str = str(PROJECT_ROOT)
    include_files: tuple[str, ...] = field(default_factory=tuple)
    timeout: int = 300
    beacon_interval: int = 3
    mcp_mode: str = "auto"
    retry_max: int = 2
    retry_backoff: tuple[int, ...] = (5, 15)
    no_preamble: bool = False
    quiet: bool = True
    model: str = DEFAULT_MODEL
    completion_marker: str = "[TASK_COMPLETE]"
    parent_task_id: str = ""
    spawned_by: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskSpec":
        retry_backoff = payload.get("retry_backoff", [5, 15])
        if isinstance(retry_backoff, str):
            parts = [part.strip() for part in retry_backoff.split(",")]
            retry_backoff_values = tuple(int(part) for part in parts if part.isdigit())
        elif isinstance(retry_backoff, list):
            retry_backoff_values = tuple(int(part) for part in retry_backoff if str(part).isdigit())
        else:
            retry_backoff_values = (5, 15)

        include_files = payload.get("include_files", [])
        include_values = tuple(str(item) for item in include_files if str(item).strip())
        return cls(
            id=str(payload.get("id", "")).strip(),
            status=str(payload.get("status", "pending")).strip().lower() or "pending",
            goal=str(payload.get("goal", "")).strip(),
            task_type=str(payload.get("task_type", "custom")).strip() or "custom",
            success_criteria=str(payload.get("success_criteria", "")).strip(),
            rounds=max(1, min(int(payload.get("rounds", 10)), 50)),
            workdir=str(payload.get("workdir", PROJECT_ROOT)).strip() or str(PROJECT_ROOT),
            include_files=include_values,
            timeout=max(1, int(payload.get("timeout", 300))),
            beacon_interval=max(1, int(payload.get("beacon_interval", 3))),
            mcp_mode=str(payload.get("mcp_mode", "auto")).strip().lower() or "auto",
            retry_max=max(0, int(payload.get("retry_max", 2))),
            retry_backoff=retry_backoff_values or (5, 15),
            no_preamble=bool(payload.get("no_preamble", False)),
            quiet=bool(payload.get("quiet", True)),
            model=str(payload.get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL,
            completion_marker=str(payload.get("completion_marker", "[TASK_COMPLETE]")).strip() or "[TASK_COMPLETE]",
            parent_task_id=str(payload.get("parent_task_id", "")).strip(),
            spawned_by=str(payload.get("spawned_by", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "goal": self.goal,
            "task_type": self.task_type,
            "success_criteria": self.success_criteria,
            "rounds": self.rounds,
            "workdir": self.workdir,
            "include_files": list(self.include_files),
            "timeout": self.timeout,
            "beacon_interval": self.beacon_interval,
            "mcp_mode": self.mcp_mode,
            "retry_max": self.retry_max,
            "retry_backoff": list(self.retry_backoff),
            "no_preamble": self.no_preamble,
            "quiet": self.quiet,
            "model": self.model,
            "completion_marker": self.completion_marker,
            "parent_task_id": self.parent_task_id,
            "spawned_by": self.spawned_by,
        }

    @property
    def workdir_path(self) -> Path:
        return Path(self.workdir).expanduser()
