"""python -m unittest discover -s tests"""

import unittest
from datetime import datetime, timedelta

from handoff.evidence import rank
from handoff.tracecheck import CONDITIONAL


class ConditionalOffers(unittest.TestCase):
    def test_offers_that_wait_on_a_request_are_dropped(self):
        for task in (
            "revert rendering change if requested",
            "revert change if Coordinator requests A-44 literal follow",
            "re-establish lineage with two new commits if requested",
            "share the logs if you want",
        ):
            self.assertRegex(task, CONDITIONAL)

    def test_real_commitments_are_kept(self):
        for task in ("post CANDIDATE", "write a stage-3 smoke", "alert if the build fails", "check if tests pass"):
            self.assertNotRegex(task, CONDITIONAL)


class Ranking(unittest.TestCase):
    def setUp(self):
        t0 = datetime(2026, 10, 5, 16, 44)
        self.promise = {"task": "drive it in a real browser", "done_when": "browser shows the UI"}
        self.turns = [
            {"id": "smoke", "ts": t0, "action": "py -3.12 ui_smoke2.py http://127.0.0.1:18181", "output": "FAILURES: 0", "narration": ""},
            {"id": "build", "ts": t0 + timedelta(minutes=1), "action": "docker build -t s2", "output": "ok", "narration": ""},
        ] + [
            {"id": f"other{i}", "ts": t0 + timedelta(minutes=5 + i), "action": f"git commit browser note {i}", "output": "", "narration": ""}
            for i in range(10)
        ]

    def test_keyword_ranking_alone_misses_the_next_action(self):
        self.assertNotIn("smoke", [t["id"] for t in rank(self.promise, self.turns, top=5)])

    def test_the_actions_right_after_the_promise_are_always_shown(self):
        shown = [t["id"] for t in rank(self.promise, self.turns, top=5, first=2)]
        self.assertEqual(shown[:2], ["smoke", "build"])
        self.assertEqual(len(shown), 5)


if __name__ == "__main__":
    unittest.main()
