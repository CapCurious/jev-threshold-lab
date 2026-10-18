# EVAL

Reproduce everything below from a fresh clone with a Jev key:

```
python3 jev_threshold_lab.py fit examples/commands.jsonl examples/questions.json --model jev-1.13.0
python3 tools/compare_claude.py
```

## Fit run

Fit run 2026-10-18, n=120 synthetic commands, model jev-1.13.0. Labels come from the generator's rules in `examples/make_fixtures.py`, never from a model. 120 calls, 0 failed, 48,465 input tokens, $0.002 at $0.042 per million input tokens, 23 s wall time.

| Threshold on certainty | Precision | Recall | F1 | Coverage |
|---|---|---|---|---|
| 0.50 | 0.968 | 1.000 | 0.984 | 1.000 |
| 0.60 | 1.000 | 1.000 | 1.000 | 0.983 |
| 0.85 (a starting point many integrations use) | 1.000 | 0.883 | 0.938 | 0.892 |
| 0.95 | 1.000 | 0.733 | 0.846 | 0.767 |

ECE 0.0541. Two wrong calls in total, both false positives (called yes, labeled no), both `echo "truncate -s 0 <file>"` (a quoted command that is never run). Bands for cost_fp 1, cost_fn 10, cost_review 0.1: act 0.60, review 0.55 (the review search starts at 0.55 because certainty is never below 0.5, so review must sit above 0.5 for anything to escalate). These numbers are on synthetic data and do not transfer; see the limits in the README.

## Jev versus claude CLI (sonnet)

<!-- compare:start -->
Run date 2026-10-18. Jev model `jev-1.13.0`; claude CLI `--model sonnet` (alias, resolved by the CLI). Synthetic fixtures, labels from the generator's rules.

| Measure | Jev | claude CLI (sonnet) |
|---|---|---|
| n (stratified, 20 yes, 20 no) | 40 | 40 |
| Accuracy against labels | 33/33 (100.0%) in the act band (certainty >= 0.85), coverage 33/40; 39/40 (97.5%) with no band | 38/40 (95.0%) (unparsed answers count wrong: 0) |
| Agreement between the two | 37/40 (92.5%) | |
| Median latency per item | 0.19 s | 3.37 s |
| Cost per 1,000 items | $0.0170 (input tokens at $0.042 per million, output free) | subscription, not metered |

Reproduce: `python3 tools/compare_claude.py --n 40 --seed 7 --model jev-1.13.0`
<!-- compare:end -->

Reading this table: Jev's in-band accuracy covers 33 of the 40 items, so it is not the same population as the claude column. n is 40 and the fixtures are synthetic, so the gap between 100% and 95% is two items. The claude CLI runs with `--setting-sources project` from an empty directory so its latency reflects the CLI and not a personal configuration; the latency gap (roughly 0.19 s against 3.4 s) is the more stable finding.
