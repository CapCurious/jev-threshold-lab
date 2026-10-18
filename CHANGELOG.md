# Changelog

## Unreleased, 2026-10-18 (iteration 1 of the quality loop)

- README cut from 1,707 to about 1,090 words: first screen is the purpose, the strongest measured number, the demo and a three-line quickstart; cost per 1,000 and 100,000 commands and a "nothing to host" line added; the Jev section is shared word for word with the sibling kits.
- jev_client: HTTP 401 or 403 raises one clear line naming JEV_API_KEY and the console URL; `fit` stops on the first auth error with exit 2.
- Demo mode no longer answers an input that has no recording; it exits 2 with one line instead of replaying the first recorded answer.
- Explainer: a "Repo on GitHub" link in the rail; the no-network test now allows that one anchor.
- Gate: tests `OK (skipped=1)`, demo byte-identical, privacy grep all classes zero except the public origin remote, leakage scan 0 findings, scorecard 14 of 15 on the working tree (the fifteenth, the explainer repo link on the live page, turns green when Pages rebuilds).

## v4 (2026-10-18)

Docs glosses from cold reads. No code changed.

What changed:
- README: first "System One" now carries a one-clause gloss (TypeSafe's name for the fast decision model family).
- README: the `bands` and `ladder` output blocks say what is abridged (question header line; for `bands` also the file-written line a real run prints).

Gates (2026-10-18):
- tests: Ran 32 tests, OK (skipped=1)
- privacy scan: 0 findings
- name, path and secret grep: pass
- Em dashes across the folder: 0 files
- README.md: 159 lines
- Tag: v0.1.0

## v3 (2026-10-18)

Two wording repairs from a second cold read. No logic changed.

What changed:
- `bands` and the `--demo` tour now print "total expected cost over 120 items: 0.20" (n is the item count of the question) so the figure is not read as a per-item cost. The per-1,000-items figure stays where it already was (EVAL.md and the explainer page).
- `ladder` names the two kinds of wrong call apart. An item Jev called yes that is labeled no is a "false positive"; an item Jev called no that is labeled yes is a "miss"; a mix prints as "wrong calls (a false positives, b misses)". The numbers line now reads `false_positives=2 misses=0`. On the committed data both wrong calls are false positives, so the ladder says "the 2 lowest-certainty false positives". EVAL.md says the same. The recall note ("positives outside the act band are misses") is unchanged, it is about positives.
- Tests: the count-aware wording test now asserts "false positive(s)"; new tests for the miss wording, the mixed wording and the bands total line (32 tests).

Gates (2026-10-18):
- tests: Ran 32 tests in 0.145s, OK (skipped=1)
- tests in an exported tree (`git archive` into a new temp dir, environment limited to PATH and HOME): Ran 32 tests in 0.058s, OK (skipped=2; the fresh-tree test and the live test skip, no .git and no key)
- privacy scan: 0 findings
- name, path and secret grep: pass
- Em dashes across the folder: 0 files

## v2 (2026-10-18)

Repairs from a cold read (a reader spent 60 seconds on the README, then ran the quickstart), then the explainer page, demo recording, skill and CI.

What changed:
- README opening line rewritten; the sweep column `FN(act)` is now `confident wrong no` in code and README, with the line "Recall counts positives outside the act band as misses." under the table and at the end of `sweep` output.
- Every number in the README names n, date and model id. The real-traffic warning carries n=60 and n=54 and says the model id was not recorded for those runs.
- Bands fix: certainty for a yes/no question is never below 0.5, so a review cut of 0.50 meant nothing could escalate. `bands` now searches review from 0.55 and act from 0.60 (review plus 0.05), caps review at act minus 0.05, and prints "certainty is never below 0.5, so review must sit above 0.5 for anything to escalate". Re-run on examples/probabilities.jsonl with --cost-fp 1 --cost-fn 10: act 0.60 (unchanged), review 0.55 (was 0.50), expected cost 0.20. policy.json, the README cookbook and EVAL.md updated.
- "Community defaults" wording replaced with "a starting point many integrations use", no citation: the TypeSafe guardrails cookbook shows 0.85 only as a permissive action threshold with review 0.35, and 0.60 does not appear there as a review cut, so the 0.85/0.60 pair could not be confirmed.
- Ladder output: the stray quote came from tokens that carried their own quote marks; tokens are now stripped. Wording is count aware ("the 2 lowest-certainty misses", one to five) with a unit test. The ladder numbers line prints `precision(0.85)` because the leakage scan read the earlier spelling, with an at sign, as an email address.
- `sweep --step 0.05` prints every fifth point. The demo tape uses it because 50 rows would scroll the header out of a 30 row terminal; the tape therefore runs `--demo sweep --step 0.05` rather than plain `--demo sweep`.
- tests/test_fresh_tree.py exports HEAD with `git archive`, runs `--demo sweep` with only PATH and HOME set and asserts the DEMO label; it skips in a tree with no .git folder (a downloaded zip). tests/test_explainer.py checks size, no network references, rail anchors and that the embedded data is current.
- docs/index.html (interactive explainer, data generated by tools/make_explainer_data.py), docs/demo.tape and docs/demo.gif, docs/HOW_IT_WAS_BUILT.md, .claude/skills/jev-threshold-lab/ (SKILL.md plus two references), .github/workflows/test.yml (python 3.11 and 3.13).

Decisions:
- The explainer's JS `pickBands` mirrors the Python and was checked in the browser: act 0.60, review 0.55, cost 0.20 and ECE 0.0541, the same as the CLI.
- Left rail, highlight not colour-coding, wrong calls marked with a highlighted label, per the page design preferences.
- Browser checks ran in the built-in pane served by `python3 -m http.server` on a free port (file:// renders as a static snapshot there).

Gates (2026-10-18):
- tests: Ran 30 tests in 0.151s, OK (skipped=1)
- privacy scan: 0 findings
- name, path and secret grep: pass
- Em dashes across the folder: 0 files
- Python 3.10 parse (`ast.parse(..., feature_version=(3, 10))`): ok for all 8 .py files
- docs/index.html: 23568 bytes (limit 153,600), no network references
- docs/demo.gif: 217450 bytes (limit 2,097,152), 16.360000 s (limit 25), recorded from docs/demo.tape with vhs 0.12.1
- Console read on docs/index.html (built-in browser, light, dark and 375 px wide, served over http): no console messages, no errors; no horizontal scroll at 375 px
- jev_client.py is identical to the shared client

Trigger test (a small model via `claude -p --setting-sources project`, 60 s timeout, run from the kit directory, fired means a Skill call for jev-threshold-lab):
- "tune a Jev threshold": fired
- "pick bands for this question": fired
- "is my Jev question calibrated": fired
- "summarize this PDF": did not fire
- "write a cover letter": did not fire

Not done: the live test did not run (no key in the environment, `JEV_LIVE=1` skipped it); the v1 live pass stands. Nothing pushed, no remote.

## v1 (2026-10-18)

First runnable version: fit, sweep, bands, reliability, ladder, `--demo`, tests, README, EVAL.

Decisions:
- Fixtures gained hard cases. The first generator (plain templates) produced 120 of 120 correct at every threshold, which would have shown nothing; it now also emits destructive commands with no scary keyword (`> file`, `cp /dev/null`, `git checkout --`) and safe commands that quote scary words (`echo "truncate ..."`, `grep "git push --force"`). Labels are still true by construction.
- `bands` needs a third cost, `--cost-review` (default 0.1), the price of sending one item outside the act band. Without it the cheapest policy is always the highest threshold.
- Recall in `sweep` counts every positive in the data, so positives outside the act band are misses at that threshold.
- `ladder` rule order: reword when precision at 0.85 is under 0.90, else split (three or more miss clusters, none above half), else reshape (two or more clusters), else cluster. Clusters group misses by command verb.
- `probabilities.jsonl` rows also carry the item `text` so `ladder` can read it.
- For non-noul questions `fit` writes zeroed metrics in `policy.json`; metrics commands cover noul only in v1.
- compare_claude runs the claude CLI with `--setting-sources project` from an empty directory (otherwise a personal configuration changes the answer format and latency).

Gates (2026-10-18):
- tests: Ran 20 tests in 0.039s, OK (skipped=1)
- tests with JEV_LIVE=1: Ran 20 tests in 1.110s, OK
- privacy scan: 0 findings
- name, path and secret grep: pass
- Python 3.10 parse (`ast.parse(..., feature_version=(3, 10))`): ok for all five .py files
- Em dashes across the folder: 0 files
- jev_client.py checksum matches the shared client: OK

Not yet built: docs/index.html, docs/demo.gif, docs/HOW_IT_WAS_BUILT.md, the skill, the CI workflow, the cold-reader pass.
