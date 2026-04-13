from __future__ import annotations

import os
import subprocess
from pathlib import Path

from gemini_unchained_daemon.bootstrap import TRUST_SCOPE, bootstrap
from gemini_unchained_daemon.gemini_json import parse_cli_output
from gemini_unchained_daemon.mcp import audit_mcp_servers, emit_allowed_mcp_args
from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon.paths import DAEMON_GEMINI_HOME, DAEMON_ROOT, HIVE_MIND_FILE
from gemini_unchained_daemon.prompting import build_round_prompt, load_persona
from gemini_unchained_daemon.swarm import read_hive_mind_excerpt
from gemini_unchained_daemon.util import load_json


def run_doctor() -> tuple[int, list[dict[str, str]]]:
    bootstrap()
    checks: list[dict[str, str]] = []

    auth_ok = all((DAEMON_GEMINI_HOME / file_name).exists() for file_name in ("oauth_creds.json", "google_accounts.json", "installation_id"))
    checks.append({
        "name": "auth_files",
        "status": "pass" if auth_ok else "fail",
        "detail": "daemon auth artifacts exist" if auth_ok else "missing one or more copied auth files",
    })

    trusted = load_json(DAEMON_GEMINI_HOME / "trustedFolders.json", {})
    trust_ok = trusted.get(TRUST_SCOPE) == "TRUST_PARENT"
    checks.append({
        "name": "trusted_folders",
        "status": "pass" if trust_ok else "fail",
        "detail": "trusted parent scope present" if trust_ok else "trusted parent scope missing",
    })

    hive_ok = HIVE_MIND_FILE.exists()
    checks.append({
        "name": "hive_mind",
        "status": "pass" if hive_ok else "fail",
        "detail": "shared hive memory file exists" if hive_ok else "runtime/HIVE_MIND.md missing",
    })

    mcp_args = emit_allowed_mcp_args("auto")
    mcp_ok = bool(mcp_args)
    checks.append({
        "name": "mcp_preflight",
        "status": "pass" if mcp_ok else "fail",
        "detail": "usable MCP allowlist emitted" if mcp_ok else "no MCP allowlist emitted",
    })

    persona_text = load_persona(DAEMON_GEMINI_HOME / "GEMINI.md")
    sample_task = TaskSpec(id="doctor", status="pending", goal="Reply with exactly OK.", quiet=True)
    sample_prompt = build_round_prompt(
        task=sample_task,
        run_id="doctor-run",
        round_number=1,
        persona_text=persona_text,
        rolling_context={
            "cumulative_summary": "No prior rounds.",
            "previous_round_output": "No prior rounds.",
            "latest_pending_state": "No prior state.",
        },
        hive_mind_excerpt=read_hive_mind_excerpt(),
    )
    injection_ok = persona_text[:120] in sample_prompt
    checks.append({
        "name": "persona_injection",
        "status": "pass" if injection_ok else "fail",
        "detail": "GEMINI.md is injected into the round prompt" if injection_ok else "GEMINI.md content missing from prompt assembly",
    })

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
        sample_task.model,
        "--allowed-mcp-server-names",
        "__none__",
    ]
    try:
        proc = subprocess.run(
            command,
            input="Reply with exactly OK",
            text=True,
            capture_output=True,
            env=env,
            cwd=str(DAEMON_ROOT),
            timeout=120,
            check=False,
        )
        parsed = parse_cli_output(proc.stdout or proc.stderr)
        headless_ok = proc.returncode == 0 and "OK" in parsed.assistant_text
        detail = "headless Gemini replied with OK" if headless_ok else (proc.stdout or proc.stderr or "no output").strip()[:240]
    except Exception as exc:  # pragma: no cover - integration path
        headless_ok = False
        detail = str(exc)
    checks.append({
        "name": "headless_prompt",
        "status": "pass" if headless_ok else "fail",
        "detail": detail,
    })

    exit_code = 0 if all(check["status"] == "pass" for check in checks) else 1
    return exit_code, checks
