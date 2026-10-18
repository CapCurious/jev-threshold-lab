# How EVAL.md was produced

Date 2026-10-18, model jev-1.13.0, 120 synthetic shell commands. The full tables are in EVAL.md
at the repository root. This note is the method.

1. Fixtures. `python3 examples/make_fixtures.py` writes 120 commands (60 destructive, 60 not)
   from a seeded generator. Labels come from the generator's rules, never from a model, so no
   model grades another model. Hard cases were added after a first set scored 120 of 120.
2. Live run. One Jev call per command (120 calls, 48,465 input tokens, $0.002) recorded to
   `examples/recorded_fit.json`, which `--demo` and the tests replay.
3. Threshold numbers. `sweep` on the recording: at certainty 0.85 precision 1.000, recall 0.883,
   coverage 0.892; ECE 0.0541. `bands` for cost_fp 1, cost_fn 10: act 0.60, review 0.55.
4. Claude comparison. `python3 tools/compare_claude.py` asks `claude -p --model sonnet` the same
   question on a stratified 40 (20 yes, 20 no): Jev 33 of 33 in its act band and 39 of 40 with
   no band, claude 38 of 40, median latency 0.19 s versus 3.37 s per item.

What this cannot see: real shell traffic, which is messier than the templates; more than one run;
confidence intervals. To reproduce, follow the commands at the top of EVAL.md.
