# jev-threshold-lab
Fit act/review/escalate thresholds for each TypeSafe Jev question on your own labeled data, with a calibration readout and a debugging ladder.

On 120 synthetic shell commands, a destructive-command gate at the common 0.85 threshold handled 89.2% of commands itself at precision 1.000; the fitted 0.60 handled 98.3% at the same precision (n=120, 2026-10-18, jev-1.13.0).

![jev-threshold-lab demo run](docs/demo.gif)
## Quickstart
```
python3 jev_threshold_lab.py --demo          # no key, offline
export JEV_API_KEY=your-key
python3 jev_threshold_lab.py fit examples/commands.jsonl examples/questions.json --model jev-1.13.0
```

Run in a clone (`git clone https://github.com/CapCurious/jev-threshold-lab && cd jev-threshold-lab`) with Python 3.10 or newer, standard library only, or try `uvx --from git+https://github.com/CapCurious/jev-threshold-lab jev-threshold-lab --demo`. The demo replays a recorded run. The fit needs a key from https://console.typesafe.ai/keys (`TYPESAFE_API_KEY` also works).

Cost, measured 2026-10-18 on jev-1.13.0 at the published $0.042 per million input tokens: fitting 120 commands took 25 seconds and $0.002, so 1,000 commands cost about $0.017 and 3.5 minutes serial, and 100,000 about $1.70 and 5.8 hours. Demo mode is free and offline. Live mode sends each command's text to TypeSafe.

Nothing to host: the explainer is a static page on GitHub Pages and the kit runs locally; there is no browser playground because the Jev API rejects browser origins (a preflight from github.io answered 400 Disallowed CORS origin on 2026-10-18). Explainer: https://capcurious.github.io/jev-threshold-lab/

## What Jev is

Jev is a hosted decision model from TypeSafe. You send it a text and one or more typed questions (yes or no, pick one from a list, or a score from 1 to 5) and it returns a probability for each answer, with no prose.

The probability is the interface. Your code sets the threshold, so the same answer can mean act, review or escalate depending on what a wrong call costs you. Calibration is a property of a population of answers, measured on a dated sample, not a guarantee on any single answer.

## Commands

- `fit ITEMS QUESTIONS`: one call per item; writes `examples/probabilities.jsonl` and `policy.json`. `--record FILE` saves responses for `--demo`, `--limit N` runs the first N.
- `sweep [--step 0.05]`: at thresholds 0.50 to 0.99 (step 0.01, or 0.05), precision, recall (positives outside the act band count as misses), F1, coverage (share of items in the act band) and `confident wrong no` (positives Jev called no inside the act band).
- `bands --cost-fp X --cost-fn Y`: picks the act and review that minimise expected cost; rewrites `policy.json`.
- `reliability`: observed rate per probability bucket, and ECE.
- `ladder`: one fix, with the numbers behind it.

Pin a versioned model id; aliases such as `jev-latest` can change. Items are JSONL: `{"id": "c001", "text": "rm -rf ./build/", "label": true}`. Questions map an id to a question: `{"destructive": {"type": "noul", "instructions": "..."}}`.

## Threshold policy

For a `noul` (yes or no) question the banded number is certainty, `max(p, 1 - p)`; for `choice` and `score` it is the returned confidence. Act at or above `act`, review at or above `review`, escalate below.

Act 0.85 and review 0.60 are a common starting point. `bands` refits them per question from the cost of a wrong yes (`--cost-fp`), a wrong no (`--cost-fn`) and one review (`--cost-review`, default 0.1): cheapest act wins, ties to the higher; review is the lowest threshold with precision within 0.05 of act's, else 0.60. Certainty is never below 0.5, so review starts at 0.55 and act at 0.60. `policy.json` records the bands with n, date and model id.

## Cookbook: destructive-command gate

The question: does this command destroy data that cannot be recovered? Fixtures: 120 synthetic commands, 60 each way, rule-labeled by `examples/make_fixtures.py`, with hard cases such as `> ./data/results.csv` (destructive, no scary word) and `echo "truncate -s 0 app.log"` (harmless). Fit run 2026-10-18, n=120, jev-1.13.0, 48,465 input tokens, $0.002, about 25 seconds:

```
thresh  precision   recall       F1  coverage   TP   FP  confident wrong no
  0.50      0.968    1.000    0.984     1.000    60    2                   0
  0.60      1.000    1.000    1.000     0.983    60    0                   0
  0.70      1.000    0.950    0.974     0.950    57    0                   0
  0.85      1.000    0.883    0.938     0.892    53    0                   0
  0.95      1.000    0.733    0.846     0.767    44    0                   0
  0.99      1.000    0.433    0.605     0.575    26    0                   0
```

At 0.85 the gate made 0 wrong calls and handled 89.2% itself; the fitted 0.60 handled 98.3%, both at precision 1.000 (n=120, 2026-10-18, jev-1.13.0). Of the 13 items outside the act band at 0.85, 7 were real positives, such as `git checkout -- src/main.py`.

`bands --cost-fp 1 --cost-fn 10` gave act 0.60, review 0.55, expected cost 0.20 over 120 items. `reliability` gave ECE 0.0541. `ladder` answered `cluster`: both false positives (c073 at 0.560, c003 at 0.590) are `echo "truncate -s 0 ..."`, a quoted command that never runs.

Ladder rungs, cheapest first: **cluster** (read the wrong calls together), **reword** (precision at 0.85 under 0.90), **reshape** (two or more failure clusters: make it a `choice`), **split** (three or more unrelated clusters: two narrower questions).

## Limits and honesty

- No explanations: the lab shows where Jev is wrong, never why.
- Every number above is on 120 synthetic, rule-labeled commands (n=120, fit run 2026-10-18, jev-1.13.0). A first version without hard cases scored 120 of 120 at every threshold (n=120, 2026-10-18, jev-1.13.0): too easy.
- Thresholds do not transfer across datasets or model versions. Refit when the data, question text or model id changes; pin a versioned id (cut points here: jev-1.13.0, 2026-10-18).
- Calibration is a population property (ECE 0.0541 over n=120, 2026-10-18, jev-1.13.0). One answer at 0.90 is not 90% likely to be right.
- Text only; image input is beta and unused. State is capped at 64k tokens per request.
- In v1 metrics cover `noul` questions; `fit` records `choice` and `score` answers with zeroed metrics.

Worked warning: a gate question on the author's shell traffic scored macro F1 0.94 on a synthetic bench (n=60 commands, run 2026-09-22) and found zero true positives at threshold 0.50 on real traffic (n=54 hand-labeled commands, 2026-09-22). The model id was not recorded; treat it as an anecdote.

## Development

```
python3 -m unittest discover -s tests          # no key needed
JEV_LIVE=1 python3 -m unittest discover -s tests   # also runs a 5-item live fit
python3 examples/make_fixtures.py              # regenerate fixtures (seeded)
python3 tools/compare_claude.py                # rebuild the Jev versus claude CLI table in EVAL.md
```

Expected: `OK (skipped=1)` in a clone without a key, `OK (skipped=2)` from a zip. Do not edit `jev_client.py`; it is shared across the Jev kits. After a refit, `python3 tools/make_explainer_data.py` updates the explainer. More: [EVAL.md](EVAL.md), [docs/HOW_IT_WAS_BUILT.md](docs/HOW_IT_WAS_BUILT.md), and `.claude/skills/jev-threshold-lab/SKILL.md` for agents.

Jev kits: [jev-cascade](https://github.com/CapCurious/jev-cascade) sends the uncertain band to a stronger model; [jev-role-ranker](https://github.com/CapCurious/jev-role-ranker) ranks job postings and flags, never rejects.

## License

MIT, see [LICENSE](LICENSE).
