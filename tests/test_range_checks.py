import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import jev_threshold_lab as lab  # noqa: E402


class RangeCheckTests(unittest.TestCase):
    def rejected(self, argv, flag):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = lab.main(argv)
        self.assertEqual(code, 2)
        errors = [line for line in stderr.getvalue().splitlines() if line.startswith("error: ")]
        self.assertEqual(len(errors), 1)
        self.assertIn(flag, errors[0])

    def test_step_must_be_in_range(self):
        self.rejected(["--demo", "sweep", "--step", "0"], "--step")
        self.rejected(["--demo", "sweep", "--step", "0.51"], "--step")

    def test_step_must_be_a_hundredth_multiple(self):
        self.rejected(["--demo", "sweep", "--step", "0.001"], "--step")

    def test_limit_must_be_positive(self):
        self.rejected(["--demo", "fit", os.path.join(ROOT, "examples", "commands.jsonl"),
                       os.path.join(ROOT, "examples", "questions.json"), "--limit", "0"], "--limit")

    def test_costs_must_be_positive(self):
        self.rejected(["--demo", "bands", "--cost-fp", "0", "--cost-fn", "1"], "--cost-fp")

    def test_stored_thresholds_must_be_ordered_and_in_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = os.path.join(tmp, "policy.json")
            with open(policy, "w", encoding="utf-8") as fh:
                json.dump({"questions": {"other": {"act": 7.0, "review": -3.0}}}, fh)
            self.rejected(["--demo", "bands", "--cost-fp", "1", "--cost-fn", "1",
                           "--policy", policy], "0 <= review < act <= 1")


if __name__ == "__main__":
    unittest.main()
