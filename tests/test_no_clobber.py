import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import jev_client  # noqa: E402
import jev_threshold_lab as lab  # noqa: E402


class StubClient(object):
    total_input_tokens = 0
    total_cost_usd = 0.0

    def __init__(self, fail_after=None):
        self.calls = 0
        self.fail_after = fail_after

    def ask(self, state, questions):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise jev_client.JevError("connection lost")
        return ({qid: {"type": "noul", "noul": 0.9} for qid in questions}, {})


class NoClobberTests(unittest.TestCase):
    def fixtures(self, tmp, count=4):
        items = os.path.join(tmp, "items.jsonl")
        questions = os.path.join(tmp, "questions.json")
        with open(items, "w", encoding="utf-8") as fh:
            for i in range(count):
                fh.write(json.dumps({"id": str(i), "text": "item " + str(i), "label": True}) + "\n")
        with open(questions, "w", encoding="utf-8") as fh:
            json.dump({"q": {"type": "noul", "instructions": "yes?"}}, fh)
        return items, questions

    def test_failure_midway_keeps_previous_output_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            items, questions = self.fixtures(tmp)
            probs, policy = os.path.join(tmp, "probs.jsonl"), os.path.join(tmp, "policy.json")
            before = b"previous bytes\n"
            with open(probs, "wb") as fh:
                fh.write(before)
            stderr = io.StringIO()
            with mock.patch.object(lab.jev_client, "client_from_env", return_value=StubClient(2)), \
                    mock.patch.object(lab.time, "sleep"), contextlib.redirect_stderr(stderr):
                code = lab.main(["fit", items, questions, "--probs", probs, "--policy", policy, "--force"])
            with open(probs, "rb") as fh:
                self.assertEqual(fh.read(), before)
        self.assertEqual(code, 2)
        errors = [line for line in stderr.getvalue().splitlines() if line.startswith("error: ")]
        self.assertEqual(errors, ["error: connection lost"])

    def test_existing_output_requires_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            items, questions = self.fixtures(tmp, 1)
            probs, policy = os.path.join(tmp, "probs.jsonl"), os.path.join(tmp, "policy.json")
            with open(probs, "wb") as fh:
                fh.write(b"keep\n")
            stderr = io.StringIO()
            with mock.patch.object(lab.jev_client, "client_from_env", return_value=StubClient()), \
                    contextlib.redirect_stderr(stderr):
                code = lab.main(["fit", items, questions, "--probs", probs, "--policy", policy])
            with open(probs, "rb") as fh:
                self.assertEqual(fh.read(), b"keep\n")
        self.assertEqual(code, 2)
        self.assertIn(probs, stderr.getvalue())
        self.assertIn("--force", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
