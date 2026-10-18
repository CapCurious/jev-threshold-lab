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


class FailingClient(object):
    total_input_tokens = 0
    total_cost_usd = 0.0

    def __init__(self, status=None):
        self.calls = 0
        self.status = status

    def ask(self, state, questions):
        self.calls += 1
        raise jev_client.JevError("last connection cause", status=self.status)


class FailFastTests(unittest.TestCase):
    def run_failure(self, client):
        with tempfile.TemporaryDirectory() as tmp:
            items = os.path.join(tmp, "items.jsonl")
            questions = os.path.join(tmp, "questions.json")
            with open(items, "w", encoding="utf-8") as fh:
                for i in range(5):
                    fh.write(json.dumps({"id": str(i), "text": "x", "label": True}) + "\n")
            with open(questions, "w", encoding="utf-8") as fh:
                json.dump({"q": {"type": "noul"}}, fh)
            stderr = io.StringIO()
            with mock.patch.object(lab.jev_client, "client_from_env", return_value=client), \
                    mock.patch.object(lab.time, "sleep"), contextlib.redirect_stderr(stderr):
                code = lab.main(["fit", items, questions, "--probs", os.path.join(tmp, "p.jsonl"),
                                 "--policy", os.path.join(tmp, "policy.json")])
        return code, stderr.getvalue()

    def test_three_consecutive_connection_failures_stop(self):
        client = FailingClient()
        code, stderr = self.run_failure(client)
        self.assertEqual((code, client.calls), (2, 3))
        self.assertEqual(stderr, "error: last connection cause\n")

    def test_auth_failure_stops_on_first_call(self):
        client = FailingClient(401)
        code, stderr = self.run_failure(client)
        self.assertEqual((code, client.calls), (2, 1))
        self.assertIn("last connection cause", stderr)

    def test_default_http_timeout_is_ten_seconds(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(jev_client.LiveClient(key="x").timeout, 10.0)


if __name__ == "__main__":
    unittest.main()
