from __future__ import annotations

import unittest

from gemini_unchained_daemon.models import TaskSpec
from gemini_unchained_daemon.prompting import build_round_prompt, derive_rolling_context


class PromptingTests(unittest.TestCase):
    def test_build_round_prompt_injects_persona_hive_and_rolling_context(self) -> None:
        task = TaskSpec(id="demo", status="pending", goal="Finish the task.", workdir="/tmp/workdir")
        prompt = build_round_prompt(
            task=task,
            run_id="run-1",
            round_number=1,
            persona_text="Alexko persona core",
            rolling_context={
                "cumulative_summary": "Round 1 summary",
                "previous_round_output": "Round 1 raw normalized output",
                "latest_pending_state": "Continue by editing file X",
            },
            hive_mind_excerpt="Prior swarm memory",
        )

        self.assertIn("# Injected Persona Context (GEMINI.md)", prompt)
        self.assertIn("Alexko persona core", prompt)
        self.assertIn("## Hive Mind Snapshot", prompt)
        self.assertIn("Prior swarm memory", prompt)
        self.assertIn("Round 1 summary", prompt)
        self.assertIn("Round 1 raw normalized output", prompt)
        self.assertIn("Continue by editing file X", prompt)
        self.assertIn("Begin the task and work toward completion.", prompt)

    def test_derive_rolling_context_prefers_continuation_prompt(self) -> None:
        rolling = derive_rolling_context(
            [
                {
                    "round": 1,
                    "assistant_text": "Started work",
                    "status_line": "STATUS: first pass",
                    "continuation_prompt": "Continue by applying the pending patch",
                    "markers": {},
                }
            ]
        )

        self.assertEqual(rolling["previous_round_output"], "Started work")
        self.assertEqual(rolling["latest_pending_state"], "Continue by applying the pending patch")

    def test_derive_rolling_context_compacts_older_rounds_when_needed(self) -> None:
        rounds = [
            {
                "round": 1,
                "assistant_text": "a" * 500,
                "status_line": "STATUS: one",
                "continuation_prompt": "continue one",
                "markers": {},
            },
            {
                "round": 2,
                "assistant_text": "b" * 500,
                "status_line": "STATUS: two",
                "continuation_prompt": "continue two",
                "markers": {},
            },
        ]

        rolling = derive_rolling_context(rounds, limit=150)

        self.assertEqual(rolling["previous_round_output"], "b" * 500)
        self.assertEqual(rolling["latest_pending_state"], "continue two")
        self.assertIn("Round 1:", rolling["cumulative_summary"])


if __name__ == "__main__":
    unittest.main()
