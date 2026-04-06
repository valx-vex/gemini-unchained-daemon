from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gemini_unchained_daemon import daemon


class DaemonTests(unittest.TestCase):
    def test_reconcile_running_treats_reaped_child_as_exited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            worker_state_file = Path(tmp_dir) / "current_run.json"
            worker_state_file.write_text('{"status": "completed"}\n', encoding="utf-8")
            state = {
                "tasks": {
                    "demo": {
                        "status": "running",
                        "pid": 12345,
                        "worker_state_file": str(worker_state_file),
                    }
                }
            }

            with (
                patch.object(daemon, "_reap_child_if_exited", return_value=True),
                patch.object(daemon, "_pid_alive", return_value=True),
            ):
                daemon.reconcile_running(state)

            self.assertEqual(state["tasks"]["demo"]["status"], "completed")
            self.assertIn("ended_at", state["tasks"]["demo"])

    def test_reconcile_running_repairs_queue_status_from_worker_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            worker_state_file = tmp_path / "current_run.json"
            worker_state_file.write_text(
                json.dumps({"status": "completed", "completion_reason": "completion_marker", "last_error": ""}) + "\n",
                encoding="utf-8",
            )
            tasks_file = tmp_path / "TASKS.json"
            tasks_file.write_text(
                json.dumps({"tasks": [{"id": "demo", "status": "running", "goal": "test"}]}, indent=2) + "\n",
                encoding="utf-8",
            )
            state = {
                "tasks": {
                    "demo": {
                        "status": "running",
                        "pid": 12345,
                        "worker_state_file": str(worker_state_file),
                    }
                }
            }

            with (
                patch.object(daemon, "_reap_child_if_exited", return_value=True),
                patch.object(daemon, "_pid_alive", return_value=False),
            ):
                daemon.reconcile_running(state, tasks_file)

            queue_payload = json.loads(tasks_file.read_text(encoding="utf-8"))
            self.assertEqual(queue_payload["tasks"][0]["status"], "completed")
            self.assertEqual(queue_payload["tasks"][0]["completion_reason"], "completion_marker")

    def test_dispatch_once_clears_stale_daemon_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tasks_file = tmp_path / "TASKS.json"
            state_file = tmp_path / "daemon_state.json"
            tasks_file.write_text('{"tasks": []}\n', encoding="utf-8")
            state_file.write_text('{"version": 1, "daemon_pid": 99999, "tasks": {}}\n', encoding="utf-8")

            with (
                patch.object(daemon, "DAEMON_STATE_FILE", state_file),
                patch.object(daemon, "ensure_bootstrapped", return_value=None),
                patch.object(daemon, "_pid_alive", return_value=False),
            ):
                state = daemon.dispatch_once(tasks_file=tasks_file, max_workers=1)

            self.assertEqual(state["daemon_pid"], 0)


if __name__ == "__main__":
    unittest.main()
