import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "examples"))

import jev_client  # noqa: E402
import jev_threshold_lab as lab  # noqa: E402
import make_fixtures  # noqa: E402


def S(label, p, text="x", i=0):
    return {"id": "i{}".format(i), "text": text, "label": label, "p": p,
            "cert": max(p, 1.0 - p)}


# (label, p) pairs: five positives, five negatives, one false positive at p 0.70,
# one false negative at p 0.30.
HAND = [(True, 0.95), (True, 0.90), (True, 0.80), (True, 0.30), (False, 0.05),
        (False, 0.10), (False, 0.70), (False, 0.02), (True, 0.60), (False, 0.40)]


def hand_scored():
    return [S(label, p, "cmd{}".format(i), i) for i, (label, p) in enumerate(HAND)]


class FixtureTests(unittest.TestCase):
    def test_same_seed_same_bytes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            make_fixtures.write(a, seed=7)
            make_fixtures.write(b, seed=7)
            for name in ("commands.jsonl", "questions.json"):
                with open(os.path.join(a, name), "rb") as fa, open(os.path.join(b, name), "rb") as fb:
                    self.assertEqual(fa.read(), fb.read())

    def test_balanced_unique_and_committed_file_matches(self):
        items = make_fixtures.build(7)
        self.assertEqual(len(items), 120)
        self.assertEqual(sum(1 for it in items if it["label"]), 60)
        self.assertEqual(len({it["text"] for it in items}), 120)
        committed = lab.load_jsonl(os.path.join(ROOT, "examples", "commands.jsonl"))
        self.assertEqual(committed, items)

    def test_other_seed_differs(self):
        self.assertNotEqual(make_fixtures.build(7), make_fixtures.build(8))


class MathTests(unittest.TestCase):
    def test_sweep_at_085(self):
        m = lab.metrics_at(hand_scored(), 0.85)
        self.assertEqual((m["n_act"], m["tp"], m["fp"], m["fn_act"]), (5, 2, 0, 0))
        self.assertAlmostEqual(m["precision"], 1.0)
        self.assertAlmostEqual(m["recall"], 0.4)
        self.assertAlmostEqual(m["coverage"], 0.5)
        self.assertAlmostEqual(m["f1"], 2 * 1.0 * 0.4 / 1.4)

    def test_sweep_at_070(self):
        m = lab.metrics_at(hand_scored(), 0.70)
        self.assertEqual((m["n_act"], m["tp"], m["fp"], m["fn_act"]), (8, 3, 1, 1))
        self.assertAlmostEqual(m["precision"], 0.75)
        self.assertAlmostEqual(m["recall"], 0.6)

    def test_sweep_grid_is_050_to_099(self):
        rows = lab.sweep(hand_scored())
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0]["t"], 0.50)
        self.assertEqual(rows[-1]["t"], 0.99)

    def test_bands_pick_expected_cut(self):
        res = lab.pick_bands(hand_scored(), cost_fp=1.0, cost_fn=10.0, cost_review=0.1)
        self.assertEqual(res["act"], 0.80)
        self.assertEqual(res["review"], 0.71)
        self.assertAlmostEqual(res["cost"], 0.4)

    def test_bands_review_floor_and_gap(self):
        for cost_fn in (1.0, 10.0, 1000.0):
            res = lab.pick_bands(hand_scored(), 1.0, cost_fn, 0.1)
            self.assertGreaterEqual(res["review"], 0.55)
            self.assertGreaterEqual(res["act"], 0.60)
            self.assertGreaterEqual(res["act"] - res["review"], 0.05 - 1e-9)

    def test_bands_on_all_correct_data_still_leave_room_to_escalate(self):
        easy = [S(True, 0.99, "a", 0), S(False, 0.01, "b", 1), S(True, 0.97, "c", 2)]
        res = lab.pick_bands(easy, 1.0, 10.0, 0.1)
        self.assertGreater(res["review"], 0.5)
        self.assertLessEqual(res["review"], res["act"] - 0.05 + 1e-9)

    def test_bands_costlier_misses_do_not_lower_the_cut(self):
        low = lab.pick_bands(hand_scored(), 1.0, 10.0, 0.1)["act"]
        high = lab.pick_bands(hand_scored(), 1.0, 1000.0, 0.1)["act"]
        self.assertGreaterEqual(high, low)

    def test_reliability_ece_matches_hand_computation(self):
        ps = [0.05, 0.05, 0.15, 0.95, 0.95, 0.85, 0.55, 0.55, 0.45, 0.95]
        labels = [False, False, True, True, True, True, True, False, False, False]
        scored = [S(lb, p, "c", i) for i, (p, lb) in enumerate(zip(ps, labels))]
        rows, ece = lab.reliability(scored)
        self.assertEqual(len(rows), 10)
        self.assertEqual(sum(r["n"] for r in rows), 10)
        # bucket errors: 2*0.05 + 0.85 + 0.45 + 2*0.05 + 0.15 + 3*(0.95 - 2/3), over 10
        self.assertAlmostEqual(ece, 0.25, places=9)
        self.assertAlmostEqual(rows[9]["observed"], 2.0 / 3.0)

    def test_certainty_for_noul_is_max_of_p_and_complement(self):
        self.assertAlmostEqual(jev_client.certainty({"type": "noul", "noul": 0.1}), 0.9)


class LadderTests(unittest.TestCase):
    RUNGS = {"cluster", "reword", "reshape", "split"}

    def good(self, n=6):
        return [S(True, 0.97, "rm -rf ./a", i) for i in range(n)] + \
               [S(False, 0.03, "ls ./a", 100 + i) for i in range(n)]

    def test_reword_when_precision_under_090(self):
        scored = self.good(3) + [S(False, 0.95, "echo hi", 200), S(False, 0.95, "echo ho", 201)]
        out = lab.ladder(scored)
        self.assertEqual(out["rung"], "reword")
        self.assertLess(out["numbers"]["precision_at_act"], 0.90)

    def test_cluster_when_misses_share_one_verb(self):
        scored = self.good() + [S(False, 0.60, "echo a b", 300), S(False, 0.62, "echo a c", 301)]
        out = lab.ladder(scored)
        self.assertEqual(out["rung"], "cluster")
        self.assertIn("a", [t for t, _ in out["shared_tokens"]])

    def test_reshape_when_two_clusters(self):
        scored = self.good() + [S(False, 0.60, "echo a", 300), S(False, 0.62, "cat b", 301)]
        self.assertEqual(lab.ladder(scored)["rung"], "reshape")

    def test_split_when_three_unrelated_clusters(self):
        scored = self.good() + [S(False, 0.60, "echo a", 300), S(False, 0.62, "cat b", 301),
                                S(False, 0.64, "head c", 302)]
        self.assertEqual(lab.ladder(scored)["rung"], "split")

    def test_wording_counts_the_false_positives_shown(self):
        base = self.good()
        for count, phrase in ((1, "the lowest-certainty false positive"),
                              (2, "the 2 lowest-certainty false positives"),
                              (5, "the 5 lowest-certainty false positives")):
            scored = base + [S(False, 0.60 + i * 0.01, "echo a{} b{}".format(i % 2, i), 300 + i)
                             for i in range(count)]
            text = lab.format_ladder(lab.ladder(scored))
            self.assertIn(phrase, text, count)
            self.assertNotIn("five lowest", text if count != 5 else "")
        six = base + [S(False, 0.60 + i * 0.01, "echo x y", 300 + i) for i in range(6)]
        self.assertIn("the 5 lowest-certainty false positives", lab.format_ladder(lab.ladder(six)))

    def test_called_no_labeled_yes_is_a_miss_not_a_false_positive(self):
        scored = self.good() + [S(True, 0.40, "echo a b", 300), S(True, 0.38, "echo a c", 301)]
        text = lab.format_ladder(lab.ladder(scored))
        self.assertIn("the 2 lowest-certainty misses", text)
        self.assertNotIn("false positive", text)
        mixed = lab.format_ladder(lab.ladder(self.good() + [S(True, 0.40, "echo a b", 300),
                                                            S(False, 0.62, "echo a c", 301)]))
        self.assertIn("wrong calls (1 false positive, 1 miss)", mixed)

    def test_shared_tokens_carry_no_stray_quotes(self):
        scored = self.good() + [S(False, 0.60, 'echo "truncate -s 0 a"', 300),
                                S(False, 0.62, 'echo "truncate -s 0 b"', 301)]
        text = lab.format_ladder(lab.ladder(scored))
        self.assertNotIn('"', text.splitlines()[1])
        self.assertIn("truncate (x2)", text)

    def test_no_misses_still_returns_a_rung(self):
        out = lab.ladder(self.good())
        self.assertIn(out["rung"], self.RUNGS)

    def test_committed_probabilities_give_a_rung(self):
        rows = lab.load_jsonl(os.path.join(ROOT, "examples", "probabilities.jsonl"))
        scored = lab.scored_rows(rows, "destructive")
        self.assertIn(lab.ladder(scored)["rung"], self.RUNGS)


class DemoTests(unittest.TestCase):
    def run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = lab.main(argv)
        return code, buf.getvalue()

    def test_demo_prints_label_first_and_every_report(self):
        code, text = self.run_main(["--demo"])
        self.assertEqual(code, 0)
        self.assertEqual(text.splitlines()[0], jev_client.DEMO_LABEL)
        for needle in ("sweep", "bands", "reliability", "ECE", "ladder:"):
            self.assertIn(needle, text)

    def test_sweep_step_prints_every_fifth_point_and_the_recall_note(self):
        code, text = self.run_main(["--demo", "sweep", "--step", "0.05"])
        self.assertEqual(code, 0)
        rows = [ln for ln in text.splitlines() if ln[:6].strip().replace(".", "").isdigit()
                and ln.startswith(" ")]
        self.assertEqual([ln.split()[0] for ln in rows],
                         ["0.50", "0.55", "0.60", "0.65", "0.70", "0.75", "0.80", "0.85",
                          "0.90", "0.95", "0.99"])
        self.assertIn("confident wrong no", text)
        self.assertIn("Recall counts positives outside the act band as misses.", text)

    def test_bands_cost_is_labeled_a_total_over_n_items(self):
        _, text = self.run_main(["--demo", "bands", "--cost-fp", "1", "--cost-fn", "10"])
        self.assertIn("total expected cost over 120 items: 0.20", text)

    def test_bands_prints_the_certainty_line(self):
        code, text = self.run_main(["--demo", "bands", "--cost-fp", "1", "--cost-fn", "10"])
        self.assertEqual(code, 0)
        self.assertIn("certainty is never below 0.5, so review must sit above 0.5 "
                      "for anything to escalate", text)

    def test_demo_fit_writes_nothing_without_paths(self):
        before = set(os.listdir(ROOT))
        code, text = self.run_main(["--demo", "fit",
                                    os.path.join(ROOT, "examples", "commands.jsonl"),
                                    os.path.join(ROOT, "examples", "questions.json")])
        self.assertEqual(code, 0)
        self.assertEqual(text.splitlines()[0], jev_client.DEMO_LABEL)
        self.assertEqual(before, set(os.listdir(ROOT)))

    def test_demo_fit_rejects_input_missing_from_recordings(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = os.path.join(tmp, "items.jsonl")
            with open(items, "w", encoding="utf-8") as fh:
                fh.write('{"id":"x","text":"unrecorded one","label":true}\n')
                fh.write('{"id":"y","text":"unrecorded two","label":false}\n')
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = lab.main(["--demo", "fit", items,
                                 os.path.join(ROOT, "examples", "questions.json")])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "error: no recorded answer for this input; demo mode "
                         "replays the bundled examples only, run live with a key\n")

    def test_live_fit_rejects_bad_api_key_once(self):
        error = urllib.error.HTTPError(jev_client.API_URL, 401, "Unauthorized", {}, None)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"JEV_API_KEY": "bad"}, clear=True), \
                mock.patch("urllib.request.urlopen", side_effect=error), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = lab.main(["fit", os.path.join(ROOT, "examples", "commands.jsonl"),
                             os.path.join(ROOT, "examples", "questions.json"), "--limit", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        lines = stderr.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("JEV_API_KEY", lines[0])
        self.assertIn("console.typesafe.ai/keys", lines[0])
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_policy_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            probs, policy = os.path.join(tmp, "p.jsonl"), os.path.join(tmp, "policy.json")
            code, _ = self.run_main(["--demo", "fit",
                                     os.path.join(ROOT, "examples", "commands.jsonl"),
                                     os.path.join(ROOT, "examples", "questions.json"),
                                     "--probs", probs, "--policy", policy])
            self.assertEqual(code, 0)
            code, _ = self.run_main(["--demo", "bands", "--probs", probs, "--policy", policy,
                                     "--cost-fp", "1", "--cost-fn", "10"])
            self.assertEqual(code, 0)
            with open(policy) as fh:
                pol = json.load(fh)
        self.assertEqual(set(pol), {"model", "fitted_on", "questions", "note"})
        q = pol["questions"]["destructive"]
        self.assertEqual(q["type"], "noul")
        self.assertEqual(set(q["metrics"]), {"precision_at_act", "recall_at_act", "ece"})
        self.assertLessEqual(q["review"], q["act"])


def _live_ready():
    if os.environ.get("JEV_LIVE") != "1":
        return False
    try:
        jev_client.get_key()
    except jev_client.JevKeyMissing:
        return False
    return True


@unittest.skipUnless(_live_ready(), "set JEV_LIVE=1 and a Jev key to run")
class LiveTests(unittest.TestCase):
    def test_fit_five_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            probs, policy = os.path.join(tmp, "p.jsonl"), os.path.join(tmp, "policy.json")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                code = lab.main(["fit", os.path.join(ROOT, "examples", "commands.jsonl"),
                                 os.path.join(ROOT, "examples", "questions.json"),
                                 "--model", "jev-1.13.0", "--limit", "5",
                                 "--probs", probs, "--policy", policy])
            self.assertEqual(code, 0)
            rows = lab.load_jsonl(probs)
            self.assertEqual(len(rows), 5)
            for row in rows:
                p = row["answers"]["destructive"]["noul"]
                self.assertTrue(0.0 <= p <= 1.0)


if __name__ == "__main__":
    unittest.main()
