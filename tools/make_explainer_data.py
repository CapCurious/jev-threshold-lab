#!/usr/bin/env python3
"""Embed the fixture probabilities into docs/index.html as one JS constant.

Reads examples/probabilities.jsonl and rewrites the block between the markers
/*DATA:start*/ and /*DATA:end*/ in docs/index.html. Each row is
[id, text, label (1 or 0), certainty, p_yes]. Run again after a refit.

    python3 tools/make_explainer_data.py            # rewrite docs/index.html
    python3 tools/make_explainer_data.py --check    # exit 1 if the page is stale
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBS = os.path.join(ROOT, "examples", "probabilities.jsonl")
PAGE = os.path.join(ROOT, "docs", "index.html")
START, END = "/*DATA:start*/", "/*DATA:end*/"


def build_rows(path=PROBS, qid=None):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            q = qid or next(k for k, a in row["answers"].items() if a.get("type") == "noul")
            p = float(row["answers"][q]["noul"])
            rows.append([row["id"], row["text"], 1 if row["label"] else 0,
                         round(float(row["certainty"][q]), 6), round(p, 6)])
    return rows


def render_block(rows):
    return "{}const ITEMS={};{}".format(START, json.dumps(rows, separators=(",", ":")), END)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    block = render_block(build_rows())
    with open(PAGE, "r", encoding="utf-8") as fh:
        page = fh.read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(page):
        print("markers not found in docs/index.html", file=sys.stderr)
        return 2
    new = pattern.sub(lambda _m: block, page, count=1)
    if "--check" in argv:
        return 0 if new == page else 1
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(new)
    print("wrote {} rows into docs/index.html".format(block.count("],[") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
