from __future__ import annotations

from pathlib import Path
from typing import Any

from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon.paths import TEMPLATES_DIR
from gemini_unchained_daemon.util import read_text


ROLLING_CONTEXT_LIMIT = 1_200_000


def load_system_preamble() -> str:
    return (TEMPLATES_DIR / "system_preamble.md").read_text(encoding="utf-8")


def load_persona(persona_path: Path) -> str:
    return read_text(persona_path).strip()


def render_include_files(include_files: tuple[str, ...]) -> str:
    if not include_files:
        return "_No included context files._"
    sections: list[str] = []
    for file_name in include_files:
        path = Path(file_name).expanduser()
        if path.exists():
            body = path.read_text(encoding="utf-8")
            sections.append(f"### {path}\n\n```text\n{body}\n```")
        else:
            sections.append(f"### {path}\n\n_Missing include file._")
    return "\n\n".join(sections)


def summarize_round(round_entry: dict[str, Any], excerpt_chars: int) -> str:
    status_line = str(round_entry.get("status_line", "")).strip()
    assistant_text = str(round_entry.get("assistant_text", "")).strip()
    if excerpt_chars > 0 and assistant_text:
        assistant_excerpt = assistant_text[:excerpt_chars]
    else:
        assistant_excerpt = ""
    markers = round_entry.get("markers", {}) or {}
    marker_bits = []
    if markers.get("completed"):
        marker_bits.append("completed")
    if markers.get("blocked"):
        marker_bits.append(f"blocked={markers['blocked']}")
    if markers.get("error"):
        marker_bits.append(f"error={markers['error']}")
    marker_text = f" [{', '.join(marker_bits)}]" if marker_bits else ""
    header = f"Round {round_entry.get('round')}: {status_line or 'no STATUS line'}{marker_text}"
    if assistant_excerpt:
        return f"{header}\nExcerpt: {assistant_excerpt}"
    return header


def derive_rolling_context(rounds: list[dict[str, Any]], limit: int = ROLLING_CONTEXT_LIMIT) -> dict[str, str]:
    if not rounds:
        return {
            "cumulative_summary": "No prior rounds.",
            "previous_round_output": "No prior rounds.",
            "latest_pending_state": "No prior state.",
        }

    previous = rounds[-1]
    older = rounds[:-1]
    previous_output = str(previous.get("assistant_text", "")).strip() or "No assistant text extracted."
    latest_pending_state = (
        str(previous.get("continuation_prompt", "")).strip()
        or str(previous.get("status_line", "")).strip()
        or summarize_round(previous, 240)
    )

    for excerpt_chars in (1600, 800, 320, 120, 0):
        summary_lines = [summarize_round(entry, excerpt_chars) for entry in older]
        cumulative_summary = "\n\n".join(summary_lines) if summary_lines else "No older rounds to summarize."
        serialized = "\n".join((cumulative_summary, previous_output, latest_pending_state))
        if len(serialized) <= limit or excerpt_chars == 0:
            return {
                "cumulative_summary": cumulative_summary,
                "previous_round_output": previous_output,
                "latest_pending_state": latest_pending_state,
            }

    return {
        "cumulative_summary": "Older rounds compacted aggressively.",
        "previous_round_output": previous_output,
        "latest_pending_state": latest_pending_state,
    }


def build_round_prompt(
    *,
    task: TaskSpec,
    run_id: str,
    round_number: int,
    persona_text: str,
    rolling_context: dict[str, str],
    hive_mind_excerpt: str = "",
) -> str:
    preamble = load_system_preamble().format(
        ROUND=round_number,
        MAX_ROUNDS=task.rounds,
        RUN_ID=run_id,
        COMPLETION_MARKER=task.completion_marker,
    ).strip()
    continuation_prompt = (
        "Begin the task and work toward completion."
        if round_number == 1
        else "Continue from the prior round, preserve persona continuity, and keep moving toward completion."
    )
    sections = [
        "# Injected Persona Context (GEMINI.md)\n\n" + persona_text.strip(),
        preamble,
        "## Task Goal\n\n" + task.goal,
        "\n".join(
            [
                "## Task Metadata",
                f"- Task ID: `{task.id}`",
                f"- Task Type: `{task.task_type}`",
                f"- Completion Marker: `{task.completion_marker}`",
                f"- Model: `{task.model}`",
                f"- Working Directory: `{task.workdir}`",
            ]
        ),
        (
            "## Hive Mind Snapshot\n\n" + (hive_mind_excerpt.strip() or "No hive memory yet.")
            if round_number == 1
            else ""
        ),
        "## Included Context Files\n\n" + render_include_files(task.include_files),
        "\n".join(
            [
                "## Rolling Context",
                "### Cumulative Summary",
                rolling_context["cumulative_summary"],
                "### Previous Round Normalized Output",
                rolling_context["previous_round_output"],
                "### Latest Known Pending State",
                rolling_context["latest_pending_state"],
            ]
        ),
        "## Continue\n\n" + continuation_prompt,
    ]
    return "\n\n".join(section.strip() for section in sections if section.strip()) + "\n"
