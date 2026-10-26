"""python -m unittest discover -s tests"""

import unittest
from pathlib import Path

from handoff.secrets import findings, redact
from handoff.trace import parse

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class ClaudeCodeTrace(unittest.TestCase):
    def setUp(self):
        self.t = parse((FIXTURES / "claude-code-trace.jsonl").read_text(encoding="utf-8"), "demo")

    def test_format_and_agent(self):
        self.assertEqual(self.t["format"], "claude-code")
        self.assertEqual(self.t["agent"], "Builder")

    def test_tool_calls_are_actions_with_their_output(self):
        acts = {a["id"]: a for a in self.t["actions"]}
        self.assertEqual(list(acts), ["t1", "t2", "t3", "t4"])
        self.assertEqual(acts["t2"]["action"], "tests/test_counter.py")
        self.assertEqual(acts["t3"]["action_type"], "Bash")
        self.assertIn("1 passed", acts["t3"]["output"])
        self.assertEqual(acts["t3"]["narration"], "Running the suite.")

    def test_sent_messages_are_talk(self):
        sent = [r for r in self.t["talk"] if r["channel"] == "sent"]
        self.assertEqual(len(sent), 2)
        self.assertIn("I'll add tests/test_counter.py", sent[0]["content"])

    def test_peer_message_keeps_its_sender_and_notices_are_skipped(self):
        received = [r for r in self.t["talk"] if r["channel"] == "received"]
        self.assertEqual([r["speaker"] for r in received], ["demo/coordinator"])
        self.assertFalse(any("task-notification" in r["content"] for r in self.t["talk"]))

    def test_secret_in_tool_output_is_redacted(self):
        out = next(a["output"] for a in self.t["actions"] if a["id"] == "t3")
        self.assertIn("TOKEN=[redacted]", out)
        self.assertEqual(self.t["redacted"], 1)


class PlainTrace(unittest.TestCase):
    def test_chat_export_has_talk_only(self):
        t = parse((FIXTURES / "nightshift-swarm.jsonl").read_text(encoding="utf-8"), "Nightshift")
        self.assertEqual(t["format"], "chat")
        self.assertEqual(t["actions"], [])
        self.assertGreater(len(t["talk"]), 3)

    def test_lines_with_an_action_become_actions(self):
        raw = (
            '{"created_at":"2026-10-20 09:00:00","speaker":"Mira","content":"I\'ll wire the probe."}\n'
            '{"created_at":"2026-10-20 09:05:00","speaker":"Mira","action":"curl -s /ready","output":"200 OK"}\n'
        )
        t = parse(raw, "ops")
        self.assertEqual([a["action"] for a in t["actions"]], ["curl -s /ready"])
        self.assertEqual(t["agent"], "Mira")


class Redaction(unittest.TestCase):
    def test_redacted_text_passes_the_export_check(self):
        clean, n = redact("password: hunter2hunter2 and token=abcdefgh12345678")
        self.assertEqual(n, 2)
        self.assertEqual(findings(clean), [])

    def test_private_key_block_goes_whole(self):
        clean, n = redact("x\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----\ny")
        self.assertEqual((clean, n), ("x\n[redacted]\ny", 1))


if __name__ == "__main__":
    unittest.main()
