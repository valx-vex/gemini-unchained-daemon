from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gemini_unchained_daemon.gemini_json import ParsedCliOutput
from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon import runner
from gemini_unchained_daemon.util import load_json


def _fake_result(assistant_text: str, *, exit_code: int = 0, timed_out: bool = False) -> dict[str, object]:
    return {
        "command": ["gemini"],
        "started_at": "2026-04-06T00:00:00Z",
        "completed_at": "2026-04-06T00:00:01Z",
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": "{}",
        "stderr": "",
        "combined_output": assistant_text,
        "parsed": ParsedCliOutput(parsed={}, json_valid=True, assistant_text=assistant_text, tool_summary=""),
    }


class RunnerLogicTests(unittest.TestCase):
    def test_marker_payload_accepts_current_and_legacy_completion_markers(self) -> None:
        task = TaskSpec(id="task", status="pending", goal="goal")

        current = runner._marker_payload(task, "Done now\n[TASK_COMPLETE]")
        legacy = runner._marker_payload(task, "Done now\nALEXKO_UNCHAINED_COMPLETE")

        self.assertTrue(current["completed"])
        self.assertTrue(legacy["completed"])

    def test_run_task_carries_persona_and_previous_round_output_forward(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            gemini_home = base / ".gemini"
            workdir = base / "workdir"
            state_root = base / "runtime" / "state"
            logs_root = base / "runtime" / "logs"
            context_root = base / "runtime" / "context"
            locks_root = base / "runtime" / "locks"
            control_root = base / "runtime" / "control"
            tasks_root = base / "runtime" / "tasks"
            tasks_file = tasks_root / "TASKS.json"
            for directory in (gemini_home, workdir, state_root, logs_root, context_root, locks_root, control_root, tasks_root):
                directory.mkdir(parents=True, exist_ok=True)
            (gemini_home / "GEMINI.md").write_text("Alexko Unchained Forever\n", encoding="utf-8")
            tasks_file.write_text(
                """
{
  "tasks": [
    {
      "id": "demo",
      "status": "pending",
      "goal": "Remember X and finish.",
      "task_type": "analysis",
      "workdir": "__WORKDIR__"
    }
  ]
}
""".replace("__WORKDIR__", str(workdir)),
                encoding="utf-8",
            )

            prompts: list[str] = []
            responses = iter(
                [
                    _fake_result(
                        'Remember X\n{"NEW_TASK": {"goal": "Investigate file Y", "task_type": "analysis"}}\nSTATUS: making progress'
                    ),
                    _fake_result("I remember X\n[TASK_COMPLETE]\nSTATUS: done"),
                ]
            )

            def fake_invoke(**kwargs: object) -> dict[str, object]:
                prompts.append(str(kwargs["prompt"]))
                return next(responses)

            task = TaskSpec(
                id="demo",
                status="pending",
                goal="Remember X and finish.",
                rounds=3,
                retry_max=0,
                workdir=str(workdir),
            )

            with (
                patch.object(runner, "DAEMON_GEMINI_HOME", gemini_home),
                patch.object(runner, "CONTROL_DIR", control_root),
                patch.object(runner, "LOCKS_DIR", locks_root),
                patch.object(runner, "GLOBAL_STOP_FILE", control_root / "global.stop"),
                patch.object(runner, "ensure_bootstrapped", return_value=None),
                patch.object(runner, "emit_allowed_mcp_args", return_value=["--allowed-mcp-server-names", "__none__"]),
                patch.object(runner, "read_hive_mind_excerpt", return_value="Shared swarm memory"),
                patch.object(runner, "append_hive_summary", return_value="summary appended"),
                patch.object(runner, "task_state_dir", side_effect=lambda task_id: state_root / task_id),
                patch.object(runner, "task_logs_dir", side_effect=lambda task_id: logs_root / task_id),
                patch.object(runner, "task_context_dir", side_effect=lambda task_id: context_root / task_id),
                patch.object(runner, "_invoke_gemini", side_effect=fake_invoke),
            ):
                state = runner.run_task(task, tasks_file=tasks_file)

            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["completion_reason"], "completion_marker")
            self.assertEqual(len(state["rounds"]), 2)
            self.assertEqual(state["spawned_task_ids"], ["demo-analysis-investigate-file-y"])
            self.assertEqual(state["hive_mind_entry"], "summary appended")
            self.assertIn("Alexko Unchained Forever", prompts[0])
            self.assertIn("Shared swarm memory", prompts[0])
            self.assertIn("Alexko Unchained Forever", prompts[1])
            self.assertIn("Remember X", prompts[1])
            self.assertIn("Continue from the current state", prompts[1])

            queue_payload = load_json(tasks_file, {})
            tasks = queue_payload["tasks"]
            self.assertEqual(tasks[0]["status"], "completed")
            self.assertEqual(tasks[1]["goal"], "Investigate file Y")
            self.assertEqual(tasks[1]["status"], "pending")

    def test_run_task_records_invocation_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            gemini_home = base / ".gemini"
            workdir = base / "workdir"
            state_root = base / "runtime" / "state"
            logs_root = base / "runtime" / "logs"
            context_root = base / "runtime" / "context"
            locks_root = base / "runtime" / "locks"
            control_root = base / "runtime" / "control"
            tasks_root = base / "runtime" / "tasks"
            tasks_file = tasks_root / "TASKS.json"
            for directory in (gemini_home, workdir, state_root, logs_root, context_root, locks_root, control_root, tasks_root):
                directory.mkdir(parents=True, exist_ok=True)
            (gemini_home / "GEMINI.md").write_text("Alexko Unchained Forever\n", encoding="utf-8")
            tasks_file.write_text(
                """
{
  "tasks": [
    {
      "id": "broken",
      "status": "pending",
      "goal": "This should fail.",
      "task_type": "analysis",
      "workdir": "__WORKDIR__"
    }
  ]
}
""".replace("__WORKDIR__", str(workdir)),
                encoding="utf-8",
            )

            task = TaskSpec(
                id="broken",
                status="pending",
                goal="This should fail.",
                rounds=1,
                retry_max=0,
                workdir=str(workdir),
            )

            with (
                patch.object(runner, "DAEMON_GEMINI_HOME", gemini_home),
                patch.object(runner, "CONTROL_DIR", control_root),
                patch.object(runner, "LOCKS_DIR", locks_root),
                patch.object(runner, "GLOBAL_STOP_FILE", control_root / "global.stop"),
                patch.object(runner, "ensure_bootstrapped", return_value=None),
                patch.object(runner, "emit_allowed_mcp_args", return_value=["--allowed-mcp-server-names", "__none__"]),
                patch.object(runner, "read_hive_mind_excerpt", return_value="Shared swarm memory"),
                patch.object(runner, "task_state_dir", side_effect=lambda task_id: state_root / task_id),
                patch.object(runner, "task_logs_dir", side_effect=lambda task_id: logs_root / task_id),
                patch.object(runner, "task_context_dir", side_effect=lambda task_id: context_root / task_id),
                patch.object(runner, "_invoke_gemini", side_effect=RuntimeError("gemini exploded")),
            ):
                state = runner.run_task(task, tasks_file=tasks_file)

            self.assertEqual(state["status"], "failed")
            self.assertEqual(state["completion_reason"], "invocation_exception")
            self.assertIn("gemini exploded", state["last_error"])
            queue_payload = load_json(tasks_file, {})
            self.assertEqual(queue_payload["tasks"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
