from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


ASSISTANT_ROLES = {"assistant", "model", "gemini"}
ASSISTANT_TYPES = {"assistant", "model", "gemini", "output_text", "message"}


@dataclass
class ParsedCliOutput:
    parsed: Any
    json_valid: bool
    assistant_text: str
    tool_summary: str


def _load_json_best_effort(raw: str) -> tuple[Any, bool]:
    raw = raw.strip()
    if not raw:
        return None, False
    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        pass

    items: list[Any] = []
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            items.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    if items:
        return items, True
    return None, False


def _extract_assistant_strings(node: Any, *, assistant_like: bool = False) -> list[str]:
    results: list[str] = []
    if isinstance(node, dict):
        role = str(node.get("role", "")).strip().lower()
        node_type = str(node.get("type", "")).strip().lower()
        current_assistant_like = assistant_like or role in ASSISTANT_ROLES or node_type in ASSISTANT_TYPES

        for key in ("text", "content", "message", "response"):
            value = node.get(key)
            if isinstance(value, str) and current_assistant_like:
                results.append(value.strip())

        if isinstance(node.get("content"), list):
            for item in node["content"]:
                results.extend(_extract_assistant_strings(item, assistant_like=current_assistant_like))

        for key, value in node.items():
            if key == "content" and isinstance(value, list):
                continue
            if isinstance(value, (dict, list)):
                results.extend(_extract_assistant_strings(value, assistant_like=current_assistant_like))
    elif isinstance(node, list):
        for item in node:
            results.extend(_extract_assistant_strings(item, assistant_like=assistant_like))
    return [item for item in results if item]


def _extract_fallback_strings(node: Any) -> list[str]:
    results: list[str] = []
    if isinstance(node, dict):
        for key in ("text", "content", "message", "response"):
            value = node.get(key)
            if isinstance(value, str):
                results.append(value.strip())
        for value in node.values():
            if isinstance(value, (dict, list)):
                results.extend(_extract_fallback_strings(value))
    elif isinstance(node, list):
        for item in node:
            results.extend(_extract_fallback_strings(item))
    return [item for item in results if item]


def _extract_tool_lines(node: Any) -> list[str]:
    lines: list[str] = []
    if isinstance(node, dict):
        looks_like_tool = any(key in node for key in ("toolName", "tool_name", "toolCalls", "name")) and (
            "tool" in str(node.get("type", "")).lower() or "tool" in "".join(node.keys()).lower()
        )
        if looks_like_tool:
            name = str(node.get("toolName") or node.get("tool_name") or node.get("name") or "tool").strip()
            status = str(node.get("status", "")).strip()
            parts = [name]
            if status:
                parts.append(status)
            lines.append(" | ".join(parts))
        for value in node.values():
            if isinstance(value, (dict, list)):
                lines.extend(_extract_tool_lines(value))
    elif isinstance(node, list):
        for item in node:
            lines.extend(_extract_tool_lines(item))
    return lines


def parse_cli_output(raw: str) -> ParsedCliOutput:
    parsed, json_valid = _load_json_best_effort(raw)
    if not json_valid:
        return ParsedCliOutput(parsed=None, json_valid=False, assistant_text="", tool_summary="")

    assistant_strings = _extract_assistant_strings(parsed)
    if not assistant_strings:
        assistant_strings = _extract_fallback_strings(parsed)
    tool_lines = _extract_tool_lines(parsed)
    assistant_text = "\n\n".join(dict.fromkeys(item for item in assistant_strings if item))
    tool_summary = "\n".join(dict.fromkeys(line for line in tool_lines if line))
    return ParsedCliOutput(
        parsed=parsed,
        json_valid=True,
        assistant_text=assistant_text.strip(),
        tool_summary=tool_summary.strip(),
    )
