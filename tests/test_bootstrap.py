from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemini_unchained_daemon.bootstrap import TRUST_SCOPE, bootstrap
from gemini_unchained_daemon.util import load_json


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_uses_supplied_daemon_root_and_copies_only_needed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_home = tmp_path / "source" / ".gemini"
            daemon_root = tmp_path / "daemon-root"
            source_home.mkdir(parents=True)

            (source_home / "oauth_creds.json").write_text('{"token": "abc"}\n', encoding="utf-8")
            (source_home / "google_accounts.json").write_text('{"accounts": []}\n', encoding="utf-8")
            (source_home / "installation_id").write_text("install-123\n", encoding="utf-8")
            (source_home / "GEMINI.md").write_text("Alexko Unchained persona\n", encoding="utf-8")
            (source_home / "history").mkdir()
            (source_home / "history" / "session.json").write_text('{"ignored": true}\n', encoding="utf-8")
            (source_home / "settings.json").write_text(
                """
{
  "security": {"auth": {"selectedType": "oauth-personal"}},
  "general": {"sessionRetention": {"warningAcknowledged": false, "enabled": true, "maxAge": "7d"}},
  "mcpServers": {
    "healthy": {"command": "node", "args": ["server.js"]},
    "remote": {"url": "https://example.test/mcp"},
    "broken": {"description": "missing command"}
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            report = bootstrap(source_home=source_home, daemon_root=daemon_root)

            self.assertEqual(report.daemon_root, daemon_root)
            self.assertTrue((daemon_root / ".gemini" / "oauth_creds.json").exists())
            self.assertTrue((daemon_root / ".gemini" / "google_accounts.json").exists())
            self.assertTrue((daemon_root / ".gemini" / "installation_id").exists())
            self.assertTrue((daemon_root / ".gemini" / "GEMINI.md").exists())
            self.assertTrue((daemon_root / ".gemini" / "policies" / "guardrails.toml").exists())
            self.assertTrue((daemon_root / "runtime" / "tasks" / "TASKS.json").exists())
            self.assertTrue((daemon_root / "runtime" / "HIVE_MIND.md").exists())
            self.assertFalse((daemon_root / ".gemini" / "history").exists())

            settings = load_json(daemon_root / ".gemini" / "settings.json", {})
            self.assertEqual(settings["model"]["name"], "auto")
            self.assertEqual(sorted(settings["mcpServers"].keys()), ["healthy", "remote"])

            trusted = load_json(daemon_root / ".gemini" / "trustedFolders.json", {})
            self.assertEqual(trusted, {TRUST_SCOPE: "TRUST_PARENT"})

            self.assertTrue((source_home / "history" / "session.json").exists())


if __name__ == "__main__":
    unittest.main()
