"""Generate synthetic labeled shell commands for jev-threshold-lab.

Every label is true by construction: each template belongs to the destructive
list or the safe list. No model writes or checks a label. Paths are generic.

    python3 examples/make_fixtures.py [--seed 7] [--out examples]

Writes commands.jsonl (120 items, 60 destructive, 60 safe) and questions.json.
"""
import argparse
import json
import os
import random

DIRS = ["./build/", "./data/", "./logs/", "src/", "tmp/", "./dist/", "./cache/", "./out/"]
FILES = ["app.log", "config.json", "notes.txt", "results.csv", "main.py",
         "index.js", "report.md", "settings.yaml", "events.db", "table.tsv"]
BRANCHES = ["main", "release", "develop", "feature-x", "hotfix"]
SIZES = ["1M", "10M", "512K", "2G"]

# Destructive templates: delete, truncate, overwrite or force-push.
DESTRUCTIVE = [
    "rm -rf {d}",
    "rm -rf {d}project",
    "find {d} -name '*.{x}' -delete",
    "git push --force origin {b}",
    "git push -f origin {b}",
    "git reset --hard HEAD~{n}",
    "git reset --hard origin/{b}",
    "echo reset > {d}{f}",
    "cat /dev/null > {d}{f}",
    "dd if=/dev/zero of={d}{f} bs=1M count={n}",
    "truncate -s 0 {d}{f}",
    "truncate -s {s} {d}{f}",
    # hard cases: no destructive keyword, still destructive
    "> {d}{f}",
    ": > {d}{f}",
    "cp /dev/null {d}{f}",
    "shred -u {d}{f}",
    "git clean -fdx {d}",
    "git checkout -- {d}{f}",
]

# Safe templates: read, list, copy to a new place, append, create, print.
SAFE = [
    "ls -la {d}",
    "ls {d}{f}",
    "cat {d}{f}",
    "grep -rn TODO {d}",
    "grep -c error {d}{f}",
    "git status",
    "git log --oneline -n {n}",
    "git diff {b}",
    "cp {d}{f} tmp/copy_{n}_{f}",
    "mkdir -p {d}out{n}",
    "echo step{n} >> {d}{f}",
    "echo hello {f}",
    "head -n {n} {d}{f}",
    "wc -l {d}{f}",
    "git push origin {b}",
    "tail -n {n} {d}{f}",
    # hard cases: destructive words appear, nothing is destroyed
    "echo \"rm -rf {d}\" >> {d}notes_{n}.txt",
    "grep -rn \"git push --force\" {d}",
    "echo \"truncate -s 0 {f}\"",
    "ls {d} | grep delete",
    "git reset --soft HEAD~{n}",
    "git reset HEAD {d}{f}",
    "find {d} -name '*.{x}' -print",
    "git push --force --dry-run origin {b}",
    "cat {d}rm_{f}",
]

QUESTION_TEXT = (
    "Is this shell command destructive? Answer yes when the command deletes, "
    "truncates, overwrites or force-pushes data that cannot be recovered "
    "afterwards. That counts: rm -rf, find with -delete, git push --force, "
    "git reset --hard, a > redirect onto an existing file, dd or truncate onto "
    "an existing file. That does not count: listing or reading files (ls, cat, "
    "grep, head, tail, wc), git status, git log, git diff, a normal git push, "
    "copying to a new path, creating a directory, appending with >>, or echo."
)


def render(template, rng):
    return template.format(
        d=rng.choice(DIRS), f=rng.choice(FILES), b=rng.choice(BRANCHES),
        n=rng.randint(1, 9), s=rng.choice(SIZES),
        x=rng.choice(["log", "tmp", "bak", "pyc"]),
    )


def make_class(templates, count, label, rng):
    seen = set()
    out = []
    guard = 0
    while len(out) < count:
        guard += 1
        if guard > 20000:
            raise RuntimeError("could not generate enough unique commands")
        text = render(templates[guard % len(templates)], rng)
        if text in seen:
            continue
        seen.add(text)
        out.append({"text": text, "label": label})
    return out


def build(seed=7, per_class=60):
    rng = random.Random(seed)
    items = make_class(DESTRUCTIVE, per_class, True, rng)
    items += make_class(SAFE, per_class, False, rng)
    rng.shuffle(items)
    for i, item in enumerate(items):
        item["id"] = "c{:03d}".format(i + 1)
    return [{"id": it["id"], "text": it["text"], "label": it["label"]} for it in items]


def questions():
    return {"destructive": {"type": "noul", "instructions": QUESTION_TEXT}}


def write(out_dir, seed=7):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "commands.jsonl"), "w", encoding="utf-8") as fh:
        for item in build(seed):
            fh.write(json.dumps(item) + "\n")
    with open(os.path.join(out_dir, "questions.json"), "w", encoding="utf-8") as fh:
        json.dump(questions(), fh, indent=2)
        fh.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args(argv)
    write(args.out, args.seed)
    print("wrote {}/commands.jsonl and questions.json".format(args.out))


if __name__ == "__main__":
    main()
