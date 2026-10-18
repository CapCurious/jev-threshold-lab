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


class InputValidationTests(unittest.TestCase):
    def run_fit(self, path):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = lab.main(["--demo", "fit", path,
                             os.path.join(ROOT, "examples", "questions.json")])
        self.assertEqual(code, 2)
        self.assertEqual(len(stderr.getvalue().splitlines()), 1)
        self.assertNotIn("Traceback", stderr.getvalue())
        return stderr.getvalue()

    def test_missing_file_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "missing.jsonl")
            text = self.run_fit(path)
        self.assertIn(path + ":0:", text)

    def test_non_utf8_file_names_line(self):
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            path = fh.name
            fh.write(b'{"id":"a","text":"x","label":true}\n\xff')
        try:
            text = self.run_fit(path)
        finally:
            os.unlink(path)
        self.assertIn(path + ":2: not UTF-8", text)

    def test_malformed_line_is_named(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            path = fh.name
            fh.write('{"id":"a","text":"x","label":true}\nnot-json\n')
        try:
            text = self.run_fit(path)
        finally:
            os.unlink(path)
        self.assertIn(path + ":2: not valid JSON", text)

    def test_missing_required_field_is_named(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            path = fh.name
            fh.write(json.dumps({"id": "a", "text": "x"}) + "\n")
        try:
            text = self.run_fit(path)
        finally:
            os.unlink(path)
        self.assertIn(path + ":1: missing required field 'label'", text)

    def test_string_boolean_labels_are_normalized_case_insensitively(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            path = fh.name
            fh.write('{"id":"a","text":"x","label":"FaLsE"}\n')
        try:
            rows = lab.load_jsonl(path)
        finally:
            os.unlink(path)
        self.assertIs(rows[0]["label"], False)

    def test_other_label_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            path = fh.name
            fh.write('{"id":"a","text":"x","label":1}\n')
        try:
            text = self.run_fit(path)
        finally:
            os.unlink(path)
        self.assertIn(path + ":1: 'label' must be true or false", text)


if __name__ == "__main__":
    unittest.main()
