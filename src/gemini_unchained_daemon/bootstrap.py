from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gemini_unchained_daemon.paths import (
    DAEMON_GEMINI_HOME,
    DAEMON_ROOT,
    DEFAULT_MODEL,
    DEFAULT_TASKS_FILE,
    HIVE_MIND_FILE,
    LIVE_GEMINI_HOME,
    TEMPLATES_DIR,
)
from gemini_unchained_daemon.util import atomic_write_json, atomic_write_text, ensure_dir, load_json


AUTH_FILES = ("oauth_creds.json", "google_accounts.json", "installation_id")
TRUST_SCOPE = str(Path.home())


@dataclass
class BootstrapReport:
    daemon_root: Path
    daemon_gemini_home: Path
    copied_files: list[str]
    missing_files: list[str]


def _copy_file_if_exists(source: Path, destination: Path, copied: list[str], missing: list[str]) -> None:
    if source.exists():
        ensure_dir(destination.parent)
        shutil.copy2(source, destination)
        copied.append(destination.name)
    else:
        missing.append(source.name)


def select_mcp_servers(source_settings: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for name, payload in (source_settings.get("mcpServers") or {}).items():
        if not isinstance(payload, dict):
            continue
        if payload.get("command") or payload.get("url"):
            selected[name] = payload
    return selected


def build_daemon_settings(source_settings: dict[str, Any]) -> dict[str, Any]:
    security_auth = (
        source_settings.get("security", {}).get("auth", {})
        if isinstance(source_settings.get("security"), dict)
        else {}
    )
    session_retention = (
        source_settings.get("general", {}).get("sessionRetention", {})
        if isinstance(source_settings.get("general"), dict)
        else {}
    )
    return {
        "security": {
            "auth": {
                "selectedType": security_auth.get("selectedType", "oauth-personal"),
            }
        },
        "mcpServers": select_mcp_servers(source_settings),
        "general": {
            "previewFeatures": True,
            "defaultApprovalMode": "auto_edit",
            "sessionRetention": {
                "warningAcknowledged": session_retention.get("warningAcknowledged", True),
                "enabled": session_retention.get("enabled", True),
                "maxAge": session_retention.get("maxAge", "30d"),
            },
        },
        "output": {
            "format": "json",
        },
        "ui": {
            "inlineThinkingMode": "off",
            "showModelInfoInChat": True,
            "showStatusInTitle": False,
            "showHomeDirectoryWarning": False,
        },
        "model": {
            "name": DEFAULT_MODEL,
        },
    }


def _write_guardrails_policy(daemon_gemini_home: Path = DAEMON_GEMINI_HOME) -> None:
    target = daemon_gemini_home / "policies" / "guardrails.toml"
    content = (TEMPLATES_DIR / "guardrails.toml").read_text(encoding="utf-8")
    atomic_write_text(target, content)


def _write_tasks_seed(tasks_file: Path = DEFAULT_TASKS_FILE) -> None:
    if not tasks_file.exists():
        atomic_write_json(tasks_file, {"tasks": []})


def _write_hive_mind_seed(hive_mind_file: Path = HIVE_MIND_FILE) -> None:
    if hive_mind_file.exists():
        return
    atomic_write_text(
        hive_mind_file,
        "# HIVE MIND\n\nShared swarm memory for Gemini Unchained workers.\n",
    )


def reseed_auth(source_home: Path = LIVE_GEMINI_HOME, daemon_gemini_home: Path = DAEMON_GEMINI_HOME) -> BootstrapReport:
    copied: list[str] = []
    missing: list[str] = []
    ensure_dir(daemon_gemini_home)
    for file_name in AUTH_FILES:
        _copy_file_if_exists(source_home / file_name, daemon_gemini_home / file_name, copied, missing)
    return BootstrapReport(
        daemon_root=daemon_gemini_home.parent,
        daemon_gemini_home=daemon_gemini_home,
        copied_files=copied,
        missing_files=missing,
    )


def bootstrap(source_home: Path = LIVE_GEMINI_HOME, daemon_root: Path = DAEMON_ROOT) -> BootstrapReport:
    daemon_gemini_home = daemon_root / ".gemini"
    runtime_root = daemon_root / "runtime"
    tasks_dir = runtime_root / "tasks"
    state_dir = runtime_root / "state"
    logs_dir = runtime_root / "logs"
    context_dir = runtime_root / "context"
    locks_dir = runtime_root / "locks"
    control_dir = runtime_root / "control"
    hive_mind_file = runtime_root / HIVE_MIND_FILE.name
    tasks_file = tasks_dir / DEFAULT_TASKS_FILE.name
    copied: list[str] = []
    missing: list[str] = []

    for directory in (daemon_root, daemon_gemini_home, runtime_root, tasks_dir, state_dir, logs_dir, context_dir, locks_dir, control_dir):
        ensure_dir(directory)

    source_settings = load_json(source_home / "settings.json", {})
    daemon_settings = build_daemon_settings(source_settings)
    atomic_write_json(daemon_gemini_home / "settings.json", daemon_settings)
    copied.append("settings.json")

    for file_name in AUTH_FILES:
        _copy_file_if_exists(source_home / file_name, daemon_gemini_home / file_name, copied, missing)

    _copy_file_if_exists(source_home / "GEMINI.md", daemon_gemini_home / "GEMINI.md", copied, missing)
    atomic_write_json(daemon_gemini_home / "trustedFolders.json", {TRUST_SCOPE: "TRUST_PARENT"})
    copied.append("trustedFolders.json")

    _write_guardrails_policy(daemon_gemini_home)
    copied.append("policies/guardrails.toml")
    _write_tasks_seed(tasks_file)
    _write_hive_mind_seed(hive_mind_file)
    copied.append("runtime/HIVE_MIND.md")

    return BootstrapReport(
        daemon_root=daemon_root,
        daemon_gemini_home=daemon_gemini_home,
        copied_files=copied,
        missing_files=missing,
    )


def ensure_bootstrapped() -> BootstrapReport:
    if not (DAEMON_GEMINI_HOME / "settings.json").exists():
        return bootstrap()
    if not (DAEMON_GEMINI_HOME / "trustedFolders.json").exists():
        return bootstrap()
    if not (DAEMON_GEMINI_HOME / "GEMINI.md").exists():
        return bootstrap()
    _write_tasks_seed()
    _write_guardrails_policy()
    _write_hive_mind_seed()
    return BootstrapReport(
        daemon_root=DAEMON_ROOT,
        daemon_gemini_home=DAEMON_GEMINI_HOME,
        copied_files=[],
        missing_files=[],
    )
