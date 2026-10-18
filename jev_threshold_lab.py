#!/usr/bin/env python3
"""jev-threshold-lab: fit, sweep and band confidence thresholds for Jev probabilities.

Labeled items plus Jev answers in; a precision/recall sweep, reliability table,
ECE, cost-sized act/review/escalate bands and a debugging-ladder recommendation
out. Writes policy.json. Stdlib only, Python 3.10 or newer.

    python3 jev_threshold_lab.py --demo                      # offline tour, no key
    python3 jev_threshold_lab.py fit examples/commands.jsonl examples/questions.json
    python3 jev_threshold_lab.py sweep
    python3 jev_threshold_lab.py bands --cost-fp 1 --cost-fn 10
    python3 jev_threshold_lab.py reliability
    python3 jev_threshold_lab.py ladder

Band rule: for a noul question the banded number is certainty = max(p, 1 - p);
an item is in the act band when certainty >= act, in review when >= review and
below act, else escalate. Thresholds do not transfer across datasets or models.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

import jev_client

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_ACT = 0.85
DEFAULT_REVIEW = 0.60
EPS = 1e-9
MIN_REVIEW = 0.55   # certainty is never below 0.5, so review must sit above it
GAP = 0.05          # act sits at least this far above review
CERTAINTY_LINE = ("certainty is never below 0.5, so review must sit above 0.5 "
                  "for anything to escalate")
NOTE = "thresholds do not transfer; refit on your data"
REPLAY = os.path.join(HERE, "examples", "recorded_fit.json")


# ---------------------------------------------------------------- pure helpers

def grid(lo=0.50, hi=0.99, step=0.01):
    count = int(round((hi - lo) / step)) + 1
    return [round(lo + i * step, 2) for i in range(count)]


def coarse_grid(step):
    """Every step-th point of the 0.50 to 0.99 grid, plus 0.99 itself."""
    every = int(round(step / 0.01))
    pts = [t for i, t in enumerate(grid()) if i % every == 0]
    if pts[-1] != 0.99:
        pts.append(0.99)
    return pts


def positive_prob(answer):
    """Probability of the positive label for a noul answer."""
    if isinstance(answer, dict) and answer.get("type") == "noul":
        return float(answer["noul"])
    raise ValueError("v1 supports noul questions for metrics; got {!r}".format(
        answer.get("type") if isinstance(answer, dict) else answer))


def scored_rows(rows, qid):
    """Reduce probability rows to [{id,label,p,cert,text}] for one noul question."""
    out = []
    for row in rows:
        ans = row["answers"][qid]
        p = positive_prob(ans)
        out.append({
            "id": row.get("id"),
            "text": row.get("text", ""),
            "label": bool(row["label"]),
            "p": p,
            "cert": max(p, 1.0 - p),
        })
    return out


def _safe_div(a, b):
    return a / b if b else None


def metrics_at(scored, t):
    """Metrics for the act band at certainty threshold t."""
    act = [s for s in scored if s["cert"] >= t - EPS]
    tp = sum(1 for s in act if s["p"] >= 0.5 and s["label"])
    fp = sum(1 for s in act if s["p"] >= 0.5 and not s["label"])
    fn = sum(1 for s in act if s["p"] < 0.5 and s["label"])
    positives = sum(1 for s in scored if s["label"])
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, positives)
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "t": t, "n_act": len(act), "tp": tp, "fp": fp, "fn_act": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "coverage": len(act) / len(scored) if scored else 0.0,
    }


def sweep(scored, thresholds=None):
    return [metrics_at(scored, t) for t in (thresholds or grid())]


def expected_cost(m, n, cost_fp, cost_fn, cost_review):
    """Cost of wrong auto-calls in the act band plus a review cost per item outside it."""
    return cost_fp * m["fp"] + cost_fn * m["fn_act"] + cost_review * (n - m["n_act"])


def pick_bands(scored, cost_fp, cost_fn, cost_review=0.1):
    """Return act, review and the cost table.

    Certainty for a yes/no question is never below 0.5, so the review search grid
    starts at MIN_REVIEW (0.55) and the act grid at review plus GAP (0.60 at the
    lowest). act is the cheapest act cut, ties to the higher; review is the lowest
    grid cut whose precision stays within 0.05 of the act precision, at most
    act - GAP, or the lower of 0.60 and act - GAP if none."""
    n = len(scored)
    costed = [(expected_cost(m, n, cost_fp, cost_fn, cost_review), m)
              for m in sweep(scored, grid(MIN_REVIEW + GAP))]
    best_cost, best = min(costed, key=lambda cm: (cm[0], -cm[1]["t"]))
    act = best["t"]
    review_top = round(act - GAP, 2)
    review = min(DEFAULT_REVIEW, review_top)
    if best["precision"] is not None:
        floor = best["precision"] - 0.05
        ok = [m["t"] for m in sweep(scored, grid(MIN_REVIEW, review_top))
              if m["precision"] is not None and m["precision"] >= floor - EPS]
        if ok:
            review = min(ok)
    return {"act": act, "review": review, "cost": best_cost, "at_act": best,
            "costs": [(c, m["t"]) for c, m in costed]}


def reliability(scored, buckets=10):
    """Equal-width buckets on the positive probability. Returns (rows, ece)."""
    bins = [[] for _ in range(buckets)]
    for s in scored:
        bins[min(int(s["p"] * buckets), buckets - 1)].append(s)
    rows = []
    ece = 0.0
    n = len(scored)
    for i, items in enumerate(bins):
        lo, hi = i / float(buckets), (i + 1) / float(buckets)
        if items:
            mean_p = sum(s["p"] for s in items) / len(items)
            observed = sum(1 for s in items if s["label"]) / float(len(items))
            ece += len(items) / float(n) * abs(mean_p - observed)
        else:
            mean_p = observed = None
        rows.append({"lo": lo, "hi": hi, "n": len(items), "mean_p": mean_p, "observed": observed})
    return rows, ece


def misses(scored):
    return [s for s in scored if (s["p"] >= 0.5) != s["label"]]


def wrong_kind(items):
    """'false positive' (called yes, labeled no), 'miss' (called no, labeled yes) or 'wrong call' (both)."""
    fps = sum(1 for s in items if not s["label"])
    if fps == len(items):
        return "false positive"
    if fps == 0:
        return "miss"
    return "wrong call"


def noun(kind, count):
    if count == 1:
        return kind
    return "misses" if kind == "miss" else kind + "s"


def tally(items):
    """'2 false positives', '3 misses' or '5 wrong calls (2 false positives, 3 misses)'."""
    kind = wrong_kind(items)
    text = "{} {}".format(len(items), noun(kind, len(items)))
    if kind == "wrong call":
        fps = sum(1 for s in items if not s["label"])
        text += " ({} {}, {} {})".format(fps, noun("false positive", fps),
                                         len(items) - fps, noun("miss", len(items) - fps))
    return text


def tokens(text):
    """Whitespace tokens with surrounding quote marks removed."""
    return [t for t in (w.strip("\"'") for w in text.split()) if t]


def cluster_key(text):
    parts = tokens(text)
    if not parts:
        return ""
    if parts[0] == "git" and len(parts) > 1:
        return "git " + parts[1]
    return parts[0]


def shared_tokens(items, minimum=2):
    counts = {}
    for s in items:
        for tok in set(tokens(s["text"])):
            counts[tok] = counts.get(tok, 0) + 1
    shared = [(tok, c) for tok, c in counts.items() if c >= minimum]
    return sorted(shared, key=lambda tc: (-tc[1], tc[0]))


def ladder(scored, act=DEFAULT_ACT):
    """Pick one rung: cluster, reword, reshape or split, with the numbers that triggered it."""
    wrong = misses(scored)
    at_act = metrics_at(scored, act)
    lowest = sorted(wrong, key=lambda s: (s["cert"], str(s["id"])))[:5]
    clusters = {}
    for s in wrong:
        clusters.setdefault(cluster_key(s["text"]), []).append(s)
    sizes = sorted(((len(v), k) for k, v in clusters.items()), reverse=True)
    biggest = sizes[0][0] / float(len(wrong)) if wrong else 0.0
    numbers = {
        "n": len(scored), "misses": len(wrong), "clusters": len(clusters),
        "false_positives": sum(1 for s in wrong if not s["label"]),
        "missed_positives": sum(1 for s in wrong if s["label"]),
        "precision_at_act": at_act["precision"], "act": act,
        "largest_cluster_share": round(biggest, 2),
        "cluster_sizes": {k: n for n, k in sizes},
    }
    shared = shared_tokens(lowest)
    shared_txt = ", ".join("{} (x{})".format(t, c) for t, c in shared[:6]) or "none"
    prec = at_act["precision"]
    prec_txt = "n/a" if prec is None else "{:.2f}".format(prec)
    wrong_txt = tally(wrong) if wrong else "0 wrong calls"
    sizes_txt = ", ".join("{}: {}".format(k, n) for n, k in sizes)

    if not wrong:
        rung = "cluster"
        msg = "No wrong calls at this fit, so there is nothing to cluster. Refit on more or harder items."
    elif prec is None or prec < 0.90:
        rung = "reword"
        msg = ("Precision at {:.2f} is {} (under 0.90) with {} false positives among {} act-band "
               "predictions of yes. Reword the instruction: list what counts and what does not, "
               "then refit and compare.").format(act, prec_txt, at_act["fp"], at_act["tp"] + at_act["fp"])
    elif len(clusters) >= 3 and biggest < 0.5:
        rung = "split"
        names = [k for _, k in sizes[:2]]
        msg = ("{} span {} unrelated clusters ({}); the largest holds {:.0%}. Split into two "
               "narrower questions, for example one about '{}' commands and one about '{}'."
               ).format(wrong_txt, len(clusters), sizes_txt, biggest, names[0], names[1])
    elif len(clusters) >= 2:
        rung = "reshape"
        opts = [k for _, k in sizes[:2]]
        msg = ("{} fall into {} clusters ({}). Reshape the noul question into a choice with "
               "options '{}', '{}' and 'safe' so the model separates them.").format(
                   wrong_txt, len(clusters), sizes_txt, opts[0], opts[1])
    else:
        rung = "cluster"
        msg = ("{}, all in one cluster ({}). {} share: {}. "
               "Read them together, then reword or add the pattern to the instruction."
               ).format(wrong_txt, sizes_txt, lowest_phrase(len(lowest), wrong_kind(lowest)).capitalize(),
                        shared_txt)
    return {"rung": rung, "message": msg, "numbers": numbers,
            "lowest_misses": [{"id": s["id"], "text": s["text"], "certainty": round(s["cert"], 3),
                               "label": s["label"]} for s in lowest],
            "shared_tokens": shared}


# ------------------------------------------------------------------- formatting

def _f(x, width=7, digits=3):
    return "{:>{w}}".format("n/a", w=width) if x is None else "{:>{w}.{d}f}".format(x, w=width, d=digits)


def format_sweep(rows):
    out = ["thresh  precision   recall       F1  coverage   TP   FP  confident wrong no"]
    for m in rows:
        out.append("{:>6.2f}  {}  {}  {}  {}  {:>4} {:>4}  {:>18}".format(
            m["t"], _f(m["precision"], 9), _f(m["recall"], 7), _f(m["f1"], 7),
            _f(m["coverage"], 8), m["tp"], m["fp"], m["fn_act"]))
    return "\n".join(out)


RECALL_NOTE = "Recall counts positives outside the act band as misses."


def format_reliability(rows, ece):
    out = ["bucket        n   mean_p  observed"]
    for r in rows:
        out.append("{:.1f}-{:.1f}  {:>7}  {}  {}".format(
            r["lo"], r["hi"], r["n"], _f(r["mean_p"], 7), _f(r["observed"], 8)))
    out.append("ECE {:.4f}".format(ece))
    return "\n".join(out)


def lowest_phrase(count, kind="miss"):
    """'the lowest-certainty false positive' for one, 'the 2 lowest-certainty false positives' for 2 to 5."""
    if count == 1:
        return "the lowest-certainty " + kind
    return "the {} lowest-certainty {}".format(count, noun(kind, count))


def format_ladder(result):
    out = ["ladder: {}".format(result["rung"]), result["message"]]
    nums = result["numbers"]
    out.append("numbers: n={n} false_positives={fp} misses={misses} clusters={clusters} precision({act:.2f})={p}".format(
        n=nums["n"], fp=nums["false_positives"], misses=nums["missed_positives"],
        clusters=nums["clusters"], act=nums["act"],
        p="n/a" if nums["precision_at_act"] is None else "{:.3f}".format(nums["precision_at_act"])))
    if result["lowest_misses"]:
        shown = [{"label": m["label"]} for m in result["lowest_misses"]]
        out.append(lowest_phrase(len(shown), wrong_kind(shown)) + ":")
        for m in result["lowest_misses"]:
            out.append("  {} cert={:.3f} label={} | {}".format(m["id"], m["certainty"], m["label"], m["text"]))
    return "\n".join(out)


# --------------------------------------------------------------------- file I/O

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def default_path(name):
    return os.path.join(HERE, name)


# ------------------------------------------------------------------ fit and policy

def prob_row(item, answers):
    return {
        "id": item["id"], "text": item["text"], "label": bool(item["label"]),
        "answers": answers,
        "certainty": {qid: round(jev_client.certainty(a), 6) for qid, a in answers.items()},
    }


def fit_items(client, items, questions, record=None, log=None):
    """One call per item. Returns (rows, failures)."""
    rows, failures = [], 0
    for i, item in enumerate(items):
        state = {"command": item["text"]}
        answers = usage = None
        for attempt in (1, 2):
            try:
                answers, usage = client.ask(state, questions)
                break
            except jev_client.JevError as exc:
                if exc.status in (401, 403) or isinstance(client, jev_client.RecordedClient):
                    raise
                if attempt == 2:
                    failures += 1
                    if log:
                        log("skip {}: {}".format(item["id"], exc))
                else:
                    time.sleep(1.0)
        if answers is None:
            continue
        rows.append(prob_row(item, answers))
        if record is not None:
            record.append({"questions": {q: {"type": v["type"]} for q, v in questions.items()},
                           "state": state, "answers": answers, "usage": usage})
        if log and (i + 1) % 20 == 0:
            log("fitted {}/{}".format(i + 1, len(items)))
    return rows, failures


def build_policy(model, rows, source, questions, existing=None):
    """policy.json per the shared schema. Defaults act 0.85 and review 0.60 unless existing."""
    policy = {
        "model": model,
        "fitted_on": {"n": len(rows), "date": datetime.date.today().isoformat(), "source": source},
        "questions": {},
        "note": NOTE,
    }
    prior = (existing or {}).get("questions", {})
    for qid, q in questions.items():
        act = prior.get(qid, {}).get("act", DEFAULT_ACT)
        review = prior.get(qid, {}).get("review", DEFAULT_REVIEW)
        policy["questions"][qid] = {
            "type": q["type"], "act": act, "review": review,
            "metrics": question_metrics(rows, qid, q["type"], act),
        }
    return policy


def question_metrics(rows, qid, qtype, act):
    if qtype != "noul":
        return {"precision_at_act": 0.0, "recall_at_act": 0.0, "ece": 0.0}
    scored = scored_rows(rows, qid)
    m = metrics_at(scored, act)
    _, ece = reliability(scored)
    return {"precision_at_act": round(m["precision"] or 0.0, 4),
            "recall_at_act": round(m["recall"] or 0.0, 4), "ece": round(ece, 4)}


def pick_question(rows, wanted=None):
    qids = [q for q, a in rows[0]["answers"].items() if a.get("type") == "noul"]
    if wanted:
        if wanted not in rows[0]["answers"]:
            raise SystemExit("question {!r} not in probabilities".format(wanted))
        return wanted
    if not qids:
        raise SystemExit("no noul question in probabilities; v1 supports noul questions")
    return qids[0]


# ------------------------------------------------------------------- CLI commands

def cmd_fit(args, out=print):
    items = load_jsonl(args.items)
    questions = load_json(args.questions)
    if args.limit:
        items = items[:args.limit]
    client = jev_client.client_from_env(demo_path=REPLAY if args.demo else None, model=args.model)
    record = [] if args.record else None
    log = None if args.demo else (lambda msg: print(msg, file=sys.stderr))
    started = time.time()
    rows, failures = fit_items(client, items, questions, record, log)
    elapsed = time.time() - started
    if args.demo:
        out(jev_client.DEMO_LABEL)
    if not rows:
        raise SystemExit("no successful calls; nothing written")
    source = os.path.basename(args.items)
    policy = build_policy(args.model, rows, source, questions)
    probs_path = args.probs or (None if args.demo else default_path("examples/probabilities.jsonl"))
    policy_path = args.policy or (None if args.demo else default_path("policy.json"))
    if probs_path:
        write_jsonl(probs_path, rows)
    if policy_path:
        write_json(policy_path, policy)
    if args.record:
        write_json(args.record, {"model": args.model, "recorded_on": policy["fitted_on"]["date"],
                                 "note": "synthetic commands; replayed by --demo", "records": record})
    out("fit: {} items, {} failed, {} input tokens, ${:.6f}, {:.1f}s wall".format(
        len(rows), failures, client.total_input_tokens, client.total_cost_usd, elapsed))
    return rows, policy


def _load_scored(args):
    path = args.probs or default_path("examples/probabilities.jsonl")
    rows = load_jsonl(path)
    qid = pick_question(rows, getattr(args, "question", None))
    return rows, qid, scored_rows(rows, qid)


def cmd_sweep(args, out=print):
    _, qid, scored = _load_scored(args)
    out("question: {}  n={}".format(qid, len(scored)))
    out(format_sweep(sweep(scored, coarse_grid(args.step) if args.step else None)))
    out(RECALL_NOTE)


def cmd_bands(args, out=print):
    rows, qid, scored = _load_scored(args)
    res = pick_bands(scored, args.cost_fp, args.cost_fn, args.cost_review)
    m = res["at_act"]
    out("question: {}  cost_fp={} cost_fn={} cost_review={}".format(
        qid, args.cost_fp, args.cost_fn, args.cost_review))
    out("act {:.2f}  review {:.2f}  total expected cost over {} items: {:.2f}".format(
        res["act"], res["review"], len(scored), res["cost"]))
    out("at act: precision {} recall {} coverage {:.3f}  wrong calls: {} fp, {} fn".format(
        _f(m["precision"], 0).strip(), _f(m["recall"], 0).strip(), m["coverage"], m["fp"], m["fn_act"]))
    out(CERTAINTY_LINE)
    policy_path = args.policy or (None if args.demo else default_path("policy.json"))
    if policy_path:
        qtype = rows[0]["answers"][qid]["type"]
        if os.path.exists(policy_path):
            policy = load_json(policy_path)
        else:
            policy = build_policy(args.model, rows, "probabilities.jsonl", {qid: {"type": qtype}})
        policy["questions"][qid] = {
            "type": qtype, "act": res["act"], "review": res["review"],
            "metrics": question_metrics(rows, qid, qtype, res["act"])}
        write_json(policy_path, policy)
        out("wrote {}".format(policy_path))
    return res


def cmd_reliability(args, out=print):
    _, qid, scored = _load_scored(args)
    rows, ece = reliability(scored)
    out("question: {}  n={}".format(qid, len(scored)))
    out(format_reliability(rows, ece))


def cmd_ladder(args, out=print):
    _, qid, scored = _load_scored(args)
    out("question: {}  n={}".format(qid, len(scored)))
    out(format_ladder(ladder(scored)))


def cmd_tour(args, out=print):
    """Offline tour on the recorded responses: fit in memory, then every report."""
    items = load_jsonl(default_path("examples/commands.jsonl"))
    questions = load_json(default_path("examples/questions.json"))
    client = jev_client.RecordedClient(REPLAY)
    rows, _ = fit_items(client, items, questions)
    qid = pick_question(rows)
    scored = scored_rows(rows, qid)
    out("fit: {} synthetic commands replayed".format(len(rows)))
    shown = sweep(scored, coarse_grid(0.05))
    out("\nsweep (every 0.05)")
    out(format_sweep(shown))
    out(RECALL_NOTE)
    res = pick_bands(scored, 1.0, 10.0)
    out("\nbands, cost_fp 1, cost_fn 10: act {:.2f}, review {:.2f}, total expected cost over {} items: {:.2f}".format(
        res["act"], res["review"], len(scored), res["cost"]))
    out(CERTAINTY_LINE)
    rel, ece = reliability(scored)
    out("\nreliability")
    out(format_reliability(rel, ece))
    out("\n" + format_ladder(ladder(scored)))


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--demo", action="store_true", default=argparse.SUPPRESS,
                        help="replay recorded responses, no key, no network")
    common.add_argument("--model", default=argparse.SUPPRESS,
                        help="Jev model id, default " + DEFAULT_MODEL + " (pin a versioned id)")
    parser = argparse.ArgumentParser(prog="jev-threshold-lab", description=__doc__.splitlines()[0])
    parser.add_argument("--demo", action="store_true", help="replay recorded responses, no key, no network")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Jev model id (pin a versioned id)")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("fit", parents=[common], help="one Jev call per item; write probabilities and policy")
    p.add_argument("items", help="JSONL of {id, text, label}")
    p.add_argument("questions", help="questions.json")
    p.add_argument("--probs", help="output probabilities.jsonl (default examples/probabilities.jsonl)")
    p.add_argument("--policy", help="output policy.json (default ./policy.json beside the module)")
    p.add_argument("--record", help="also write a recorded-response file for --demo")
    p.add_argument("--limit", type=int, help="only the first N items")
    p.set_defaults(func=cmd_fit)

    for name, fn, text in (("sweep", cmd_sweep, "precision, recall, F1, coverage per threshold"),
                           ("bands", cmd_bands, "pick act and review that minimise expected cost"),
                           ("reliability", cmd_reliability, "ten buckets, observed accuracy, ECE"),
                           ("ladder", cmd_ladder, "one debugging recommendation with its numbers")):
        q = sub.add_parser(name, parents=[common], help=text)
        q.add_argument("--probs", help="probabilities.jsonl (default examples/probabilities.jsonl)")
        q.add_argument("--question", help="question id (default: first noul question)")
        if name == "sweep":
            q.add_argument("--step", type=float, default=None,
                           help="print every STEP (a multiple of 0.01, e.g. 0.05) instead of every 0.01")
        if name == "bands":
            q.add_argument("--cost-fp", type=float, required=True, help="cost of a wrong yes in the act band")
            q.add_argument("--cost-fn", type=float, required=True, help="cost of a wrong no in the act band")
            q.add_argument("--cost-review", type=float, default=0.1,
                           help="cost of sending one item to review or escalate (default 0.1)")
            q.add_argument("--policy", help="policy.json to rewrite (default ./policy.json beside the module)")
        q.set_defaults(func=fn)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.demo and args.cmd != "fit":
        print(jev_client.DEMO_LABEL)
    try:
        if args.cmd is None:
            if not args.demo:
                build_parser().print_help()
                return 0
            cmd_tour(args)
            return 0
        args.func(args)
        return 0
    except jev_client.JevKeyMissing as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    except (jev_client.JevError, FileNotFoundError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2 if isinstance(exc, jev_client.JevError) else 1


if __name__ == "__main__":
    sys.exit(main())
