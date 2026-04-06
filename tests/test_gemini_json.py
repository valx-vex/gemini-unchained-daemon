from __future__ import annotations

import unittest

from gemini_unchained_daemon.gemini_json import parse_cli_output


class GeminiJsonTests(unittest.TestCase):
    def test_parse_cli_output_extracts_response_field(self) -> None:
        parsed = parse_cli_output('{"session_id":"abc","response":"OK","stats":{"models":{}}}')

        self.assertTrue(parsed.json_valid)
        self.assertEqual(parsed.assistant_text, "OK")


if __name__ == "__main__":
    unittest.main()
