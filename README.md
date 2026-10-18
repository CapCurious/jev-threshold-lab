# jev-threshold-lab

Fit act/review/escalate thresholds for each TypeSafe Jev question on your own labeled data, with a calibration readout and a debugging ladder.

![jev-threshold-lab demo: fit, sweep, bands, reliability and ladder in one run](docs/demo.gif)

Try the thresholds in your browser: [docs/index.html](docs/index.html) (https://capcurious.github.io/jev-threshold-lab/). Drag act and review over 120 synthetic commands and watch precision, recall, coverage and cost move.

```
$ python3 jev_threshold_lab.py --demo      # abridged; recorded fit, n=120, 2026-10-18, jev-1.13.0
DEMO (recorded response)
fit: 120 synthetic commands replayed

sweep (every 0.05)
thresh  precision   recall       F1  coverage   TP   FP  confident wrong no
  0.50      0.968    1.000    0.984     1.000    60    2                   0
  0.85      1.000    0.883    0.938     0.892    53    0                   0
  0.95      1.000    0.733    0.846     0.767    44    0                   0

bands, cost_fp 1, cost_fn 10: act 0.60, review 0.55, total expected cost over 120 items: 0.20
ECE 0.0541
ladder: cluster
```

## What Jev is

Jev is a hosted decision model from TypeSafe (System One (TypeSafe's name for this family of fast decision models, after the fast and slow thinking distinction)). You send it a JSON state and a plain-language question of a fixed type: yes/no (`noul`, returns a probability), pick one (`choice`), or a 1 to 5 `score`. It answers with calibrated numbers and no prose. There are no explanations by design.

That makes it programmable. The model returns a probability and your code owns the policy: act automatically above one number, send to a person between two, escalate below. You can change a threshold without re-running inference, and each question can have its own. This repo is the tool for choosing those numbers.

## Install

Python 3.10 or newer, standard library only.

```
git clone https://github.com/CapCurious/jev-threshold-lab && cd jev-threshold-lab
python3 jev_threshold_lab.py --demo
```

Or with uv: `uvx --from git+https://github.com/CapCurious/jev-threshold-lab jev-threshold-lab --demo`

## Quickstart (60 seconds)

1. Offline, no key: `python3 jev_threshold_lab.py --demo`. It replays recorded responses and prints `DEMO (recorded response)` first.
2. Live, with your own key (create one at https://console.typesafe.ai/keys):

```
export JEV_API_KEY=...        # TYPESAFE_API_KEY also works
python3 jev_threshold_lab.py fit examples/commands.jsonl examples/questions.json --model jev-1.13.0
python3 jev_threshold_lab.py sweep
python3 jev_threshold_lab.py bands --cost-fp 1 --cost-fn 10
python3 jev_threshold_lab.py reliability
python3 jev_threshold_lab.py ladder
```

120 calls cost about $0.002 and take about 25 seconds (measured on jev-1.13.0, 2026-10-18, n=120). Pin a versioned model id as above; aliases such as `jev-latest` can change under you.

| Command | What it does |
|---|---|
| `fit ITEMS QUESTIONS` | One call per item. Writes `examples/probabilities.jsonl` and `policy.json`. `--record FILE` saves the responses for `--demo`. `--limit N` runs the first N. |
| `sweep [--step 0.05]` | Thresholds 0.50 to 0.99 in steps of 0.01 (or every 0.05 with `--step`): precision, recall, F1, coverage, and `confident wrong no` (items in the act band that Jev called no and the label says yes). |
| `bands --cost-fp X --cost-fn Y` | Picks act and review that minimise expected cost, rewrites `policy.json`. |
| `reliability` | Ten buckets on the predicted probability, observed rate per bucket, ECE. |
| `ladder` | One recommendation with the numbers that triggered it. |

Input is JSONL, one object per line: `{"id": "c001", "text": "rm -rf ./build/", "label": true}`. The question file maps an id to a question: `{"destructive": {"type": "noul", "instructions": "..."}}`. In v1 the metrics commands work on `noul` questions.

## Threshold policy

For a `noul` question the banded number is certainty, `max(p, 1 - p)`, so a confident no acts as readily as a confident yes. For `choice` and `score` it is the returned confidence. An item is in the act band at or above `act`, in review at or above `review` and below `act`, and escalates below `review`.

Act 0.85 and review 0.60 are a starting point many integrations use. Each question needs its own bands, sized to the cost of a wrong call, and `bands` refits them: you give the cost of a wrong yes (`--cost-fp`), a wrong no (`--cost-fn`) and, optionally, of sending one item to a person (`--cost-review`, default 0.1). It sweeps the grid and takes the cheapest act threshold, ties going to the higher one. The review threshold is the lowest one whose precision stays within 0.05 of the precision at act, or 0.60 if there is none.

Certainty is never below 0.5, so review must sit above 0.5 for anything to escalate. The `bands` search therefore starts review at 0.55 and act at review plus 0.05 (0.60 at the lowest), and prints the line `certainty is never below 0.5, so review must sit above 0.5 for anything to escalate` with every result.

`policy.json` (written by `fit` and `bands`) records the result:

```json
{"model": "jev-1.13.0",
 "fitted_on": {"n": 120, "date": "2026-10-18", "source": "commands.jsonl"},
 "questions": {"destructive": {"type": "noul", "act": 0.6, "review": 0.55,
   "metrics": {"precision_at_act": 1.0, "recall_at_act": 1.0, "ece": 0.0541}}},
 "note": "thresholds do not transfer; refit on your data"}
```

Recall in the sweep counts every positive in the data, so a positive that falls outside the act band is a miss at that threshold. Coverage is the share of items inside the act band. `confident wrong no` counts the positives that Jev answered no with certainty inside the act band, the costliest kind of miss for a gate.

## Cookbook: a gate for destructive shell commands

Question (`examples/questions.json`): is this command destructive, meaning it deletes, truncates, overwrites or force-pushes data that cannot be recovered afterwards. The instruction lists what counts and what does not. Fixtures: 120 synthetic commands, 60 each way, labeled by the rules that generated them (`examples/make_fixtures.py`), including hard cases both ways: `> ./data/results.csv` (destroys data, no scary keyword) and `echo "truncate -s 0 app.log"` (scary words, destroys nothing).

Fit run 2026-10-18, n=120, model jev-1.13.0, 48,465 input tokens, $0.002:

```
thresh  precision   recall       F1  coverage   TP   FP  confident wrong no
  0.50      0.968    1.000    0.984     1.000    60    2                   0
  0.60      1.000    1.000    1.000     0.983    60    0                   0
  0.70      1.000    0.950    0.974     0.950    57    0                   0
  0.85      1.000    0.883    0.938     0.892    53    0                   0
  0.95      1.000    0.733    0.846     0.767    44    0                   0
  0.99      1.000    0.433    0.605     0.575    26    0                   0
```

Recall counts positives outside the act band as misses.

At 0.85 the gate never auto-approved or auto-blocked a wrong command here (precision 1.000, 0 wrong calls; n=120, 2026-10-18, jev-1.13.0), and it handled 89.2% of items itself. The other 13 items fell outside the act band (review or escalate), and 7 of them were real positives such as `cp /dev/null ./build/results.csv` and `git checkout -- src/main.py`.

```
$ python3 jev_threshold_lab.py bands --cost-fp 1 --cost-fn 10
act 0.60  review 0.55  total expected cost over 120 items: 0.20
at act: precision 1.000 recall 1.000 coverage 0.983  wrong calls: 0 fp, 0 fn
certainty is never below 0.5, so review must sit above 0.5 for anything to escalate
```

(abridged: the question header line and the file-written line are omitted)

```
$ python3 jev_threshold_lab.py ladder
ladder: cluster
2 false positives, all in one cluster (echo: 2). The 2 lowest-certainty false positives share: -s (x2), 0 (x2), echo (x2), truncate (x2). Read them together, then reword or add the pattern to the instruction.
numbers: n=120 false_positives=2 misses=0 clusters=1 precision(0.85)=1.000
the 2 lowest-certainty false positives:
  c073 cert=0.560 label=False | echo "truncate -s 0 config.json"
  c003 cert=0.590 label=False | echo "truncate -s 0 results.csv"
```

(abridged: the question header line is omitted; `ladder` writes no file)

Reliability on the same run (n=120, 2026-10-18, jev-1.13.0): ECE 0.0541, with the two false positives sitting in the 0.5 to 0.6 bucket (mean probability 0.575, observed rate 0.0). The ladder points at the one pattern worth fixing: commands that quote a destructive command without running it.

The debugging ladder, from cheapest to dearest: **cluster** (read the wrong calls together and name what they share), **reword** (precision at 0.85 under 0.90 means the instruction is the problem), **reshape** (two or more distinct failure clusters: turn the noul question into a choice), **split** (wrong calls spread over three or more unrelated clusters: write two narrower questions).

## Limits and honesty

- No explanations. Jev returns numbers, so the lab can tell you where it is wrong, not why.
- The fixtures are synthetic, written by rules, and dated. Every number above is on 120 synthetic commands (n=120, fit run 2026-10-18, jev-1.13.0). A first version of the fixtures with no hard cases scored 120 of 120 at every threshold (n=120, 2026-10-18, jev-1.13.0), which says only that the bench was easy.
- Thresholds do not transfer across datasets or model versions. Refit when the data, the question text or the model id changes, and pin a versioned id (every cut point here was fitted on jev-1.13.0, 2026-10-18).
- Calibration is a population property, not a per-answer guarantee. ECE is measured over a set (0.0541 over n=120, 2026-10-18, jev-1.13.0); one answer at 0.90 is not 90% likely to be right.
- Text only. Image input is beta and not used here. State is capped at 64k tokens per request.
- In v1 the metrics commands cover `noul` questions; `fit` records `choice` and `score` answers but writes zeroed metrics for them.

Worked warning: on the author's own shell traffic a gate question scored macro F1 0.94 on a synthetic bench (n=60 commands, run 2026-09-22) and then found zero true positives at threshold 0.50 on real traffic (n=54 hand-labeled commands, 2026-09-22). The Jev model id was not recorded for either run, so read it as an anecdote about method, not a benchmark. It is why thresholds are refit per dataset.

## Development

```
python3 -m unittest discover -s tests          # no key needed
JEV_LIVE=1 python3 -m unittest discover -s tests   # also runs a 5-item live fit
python3 examples/make_fixtures.py              # regenerate fixtures (seeded)
python3 tools/compare_claude.py                # rebuild the Jev versus claude CLI table in EVAL.md
```

Expected: `OK (skipped=1)` in a git clone without a key (the live test is skipped), and `OK (skipped=2)` from a downloaded zip, where the fresh-tree test also skips because there is no `.git` folder. `jev_client.py` is a shared client copied unchanged between the Jev kits; do not edit it here.

See [EVAL.md](EVAL.md) for the Jev versus claude CLI comparison, [docs/index.html](docs/index.html) for the interactive explainer (GitHub Pages once published), [docs/HOW_IT_WAS_BUILT.md](docs/HOW_IT_WAS_BUILT.md) for how the kit was built and what it did not measure, and the skill at `.claude/skills/jev-threshold-lab/SKILL.md` for agents. After a refit, `python3 tools/make_explainer_data.py` re-embeds the fixture data in the explainer.

## License

MIT, see [LICENSE](LICENSE).
