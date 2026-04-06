from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from gemini_unchained_daemon.paths import DAEMON_GEMINI_HOME
from gemini_unchained_daemon.util import load_json


def _command_health(command: str, args: list[str]) -> tuple[bool, str]:
    if not command.strip():
        return False, "missing_command"
    if command.startswith("/"):
        path = Path(command)
        if not path.exists():
            return False, "missing_path"
        if not os.access(path, os.X_OK):
            return False, "not_executable"
        return True, f"ok:{path}"
    resolved = shutil.which(command)
    if not resolved:
        return False, "command_not_found"
    return True, f"ok:{resolved}"


def audit_mcp_servers(settings_path: Path | None = None) -> list[dict[str, Any]]:
    settings_file = settings_path or (DAEMON_GEMINI_HOME / "settings.json")
    settings = load_json(settings_file, {})
    servers = settings.get("mcpServers") or {}
    results: list[dict[str, Any]] = []
    for name, payload in sorted(servers.items()):
        if not isinstance(payload, dict):
            results.append({"name": name, "healthy": False, "reason": "invalid_config"})
            continue
        if payload.get("url"):
            results.append({"name": name, "healthy": True, "reason": "remote_url"})
            continue
        args = payload.get("args") if isinstance(payload.get("args"), list) else []
        healthy, reason = _command_health(str(payload.get("command", "")), [str(item) for item in args])
        results.append({"name": name, "healthy": healthy, "reason": reason})
    return results


def emit_allowed_mcp_args(mode: str, settings_path: Path | None = None) -> list[str]:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "on":
        return []
    if normalized_mode == "off":
        return ["--allowed-mcp-server-names", "__none__"]

    healthy_names = [entry["name"] for entry in audit_mcp_servers(settings_path) if entry["healthy"]]
    if not healthy_names:
        return ["--allowed-mcp-server-names", "__none__"]
    return ["--allowed-mcp-server-names", *healthy_names]

