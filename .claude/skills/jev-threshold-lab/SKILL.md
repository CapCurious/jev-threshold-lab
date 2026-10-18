---
name: jev-threshold-lab
description: Fit act, review and escalate thresholds for a TypeSafe Jev question on labeled data, check its calibration, and debug a weak question. Use when the user says "tune a Jev threshold", "pick bands for this question", or "is my Jev question calibrated". Not for summarizing documents or writing text.
---

# jev-threshold-lab

Takes labeled items and the probabilities Jev returned for them, and prints the numbers needed
to choose two cut points per question: precision, recall and coverage per threshold, the
cheapest act and review bands for a given cost of being wrong, a reliability table with ECE,
and one debugging recommendation. Writes the result to `policy.json`.

## When to use

- The user has a Jev yes/no question and labeled examples and asks where to put the cut points.
- The user asks whether a question's probabilities can be trusted (calibration, ECE).
- A question misbehaves and the user wants to know whether to reword, reshape or split it.

## When not to use

- No labels. The lab measures against labels; without them it can only show a distribution.
- Thresholds for another dataset or model version. They do not transfer; refit.
- Choice and score questions for the metrics commands: they cover yes/no (`noul`) only.

## Commands

Run from the kit directory. Python 3.10 or newer, standard library only.

```
python3 jev_threshold_lab.py --demo                          # offline tour, no key
export JEV_API_KEY=YOUR_KEY    # TYPESAFE_API_KEY also works
python3 jev_threshold_lab.py fit ITEMS.jsonl QUESTIONS.json --model jev-1.13.0
python3 jev_threshold_lab.py sweep --step 0.05
python3 jev_threshold_lab.py bands --cost-fp 1 --cost-fn 10
python3 jev_threshold_lab.py reliability
python3 jev_threshold_lab.py ladder
```

- `--demo` replays recorded answers, needs no key and no network, and prints
  `DEMO (recorded response)` first. Offer it first.
- `bands` needs the cost of a wrong yes (`--cost-fp`) and of a wrong no (`--cost-fn`); ask for
  them, do not guess. It rewrites `policy.json`.
- Pin a versioned model id; aliases move. Never print or log the key.

## Reading the result

- Certainty for a yes/no question is `max(p, 1 - p)`, never below 0.5, so review must sit above
  0.5 for anything to escalate.
- `confident wrong no` counts positives that Jev answered no inside the act band.
- Ladder rungs, cheapest first: cluster, reword, reshape, split.
- Fixtures are synthetic and dated. Say that thresholds do not transfer when you report.

Question text and why it is narrow: references/questions.md. How the numbers were measured: references/eval.md.
