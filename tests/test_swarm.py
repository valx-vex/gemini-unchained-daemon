from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon.swarm import append_hive_summary, extract_new_task_payloads, read_hive_mind_excerpt, register_generated_tasks
from gemini_unchained_daemon.util import load_json


class SwarmTests(unittest.TestCase):
    def test_extract_new_task_payloads_finds_multiple_json_blocks(self) -> None:
        text = """
Working...
{"NEW_TASK": {"goal": "Map repo structure", "task_type": "analysis"}}
And another:
{"NEW_TASK": {"goal": "Write migration patch", "task_type": "implementation"}}
"""

        payloads = extract_new_task_payloads(text)

        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["goal"], "Map repo structure")
        self.assertEqual(payloads[1]["task_type"], "implementation")

    def test_register_generated_tasks_appends_pending_child_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_file = Path(tmp_dir) / "TASKS.json"
            tasks_file.write_text(
                """
{
  "tasks": [
    {
      "id": "parent",
      "status": "running",
      "goal": "Parent goal",
      "task_type": "analysis",
      "workdir": "/tmp/workdir"
    }
  ]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            parent_task = TaskSpec(id="parent", status="running", goal="Parent goal", task_type="analysis", workdir="/tmp/workdir")

            added = register_generated_tasks(
                tasks_file,
                parent_task,
                '{"NEW_TASK": {"goal": "Inspect config", "task_type": "analysis"}}',
            )
            added_again = register_generated_tasks(
                tasks_file,
                parent_task,
                '{"NEW_TASK": {"goal": "Inspect config", "task_type": "analysis"}}',
            )

            payload = load_json(tasks_file, {})
            self.assertEqual(len(added), 1)
            self.assertEqual(len(added_again), 0)
            self.assertEqual(len(payload["tasks"]), 2)
            self.assertEqual(payload["tasks"][1]["status"], "pending")
            self.assertEqual(payload["tasks"][1]["parent_task_id"], "parent")

    def test_hive_mind_summary_and_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            hive_mind_file = Path(tmp_dir) / "HIVE_MIND.md"
            task = TaskSpec(id="done", status="completed", goal="Complete the mission.")
            state = {
                "rounds": [
                    {
                        "assistant_text": "Mission complete with three fixes in place.",
                        "status_line": "STATUS: mission complete",
                    }
                ],
                "spawned_task_ids": ["child-1"],
            }

            entry = append_hive_summary(task, state, hive_mind_file=hive_mind_file)
            excerpt = read_hive_mind_excerpt(hive_mind_file=hive_mind_file)

            self.assertIn("Task `done` completed", entry)
            self.assertIn("child-1", entry)
            self.assertIn("Task `done` completed", excerpt)


if __name__ == "__main__":
    unittest.main()
