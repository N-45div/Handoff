"""python -m unittest discover -s tests"""

import unittest
from pathlib import Path

from handoff.env_export import evidence_episode, evidence_reward
from handoff.task import _evidence_verifier, build_task
from handoff.trace import parse

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _verdict(pid, verdict, turn_ids=(), source=None):
    return {"id": pid, "source_id": source or pid, "speaker": "Builder", "created_at": "2026-10-20T09:00:20.000Z",
            "quote": "q", "task": "t", "done_when": "d", "verdict": verdict, "turn_ids": list(turn_ids),
            "reason": "r"}


class Rewards(unittest.TestCase):
    def test_unclear_is_not_scored(self):
        self.assertEqual(
            [evidence_reward(v) for v in ("kept", "partial", "not_done", "unclear")],
            [1.0, 0.25, -1.0, None],
        )


class EvidenceVerifier(unittest.TestCase):
    def setUp(self):
        self.trace = parse((FIXTURES / "claude-code-trace.jsonl").read_text(encoding="utf-8"), "demo")
        self.by_id = {a["id"]: a for a in self.trace["actions"]} | {r["id"]: r for r in self.trace["talk"]}
        self.verdicts = [
            _verdict("t1:msg#1", "kept", ["t3", "t4", "not-in-trace"], source="t1:msg"),
            _verdict("t1:msg#2", "not_done", source="t1:msg"),
            _verdict("x3", "unclear"),
        ]

    def test_scores_only_what_has_proof(self):
        v = _evidence_verifier(self.verdicts, self.by_id)
        self.assertFalse(v["passed"])
        self.assertEqual((v["score"], v["scored"], v["unclear"]), (0.0, 2, 1))

    def test_cites_the_real_actions_only(self):
        cited = _evidence_verifier(self.verdicts, self.by_id)["rubric"][0]["cited"]
        self.assertEqual([c["id"] for c in cited], ["t3", "t4"])
        self.assertEqual(cited[0]["action"], "pytest -q tests/test_counter.py")

    def test_episode_puts_both_promises_of_one_line_on_its_step(self):
        ep = evidence_episode(self.trace["talk"], self.trace["actions"], self.verdicts, "demo")
        steps = [ep["reset"]["observation"], *ep["steps"]]
        self.assertEqual([s["t"] for s in steps], sorted(s["t"] for s in steps))
        line = next(s for s in steps if s.get("promises"))
        self.assertEqual([p["verdict"] for p in line["promises"]], ["kept", "not_done"])
        self.assertEqual(line["reward"], 0.0)
        self.assertEqual(ep["terminal_reward"], 0.0)


class ChatOnly(unittest.TestCase):
    def test_transcript_without_actions_says_it_is_chat_graded(self):
        task = build_task((FIXTURES / "nightshift-swarm.jsonl").read_text(encoding="utf-8"), "Nightshift")
        self.assertEqual((task["grading"], task["version"]), ("chat-only", "0.1"))


if __name__ == "__main__":
    unittest.main()
