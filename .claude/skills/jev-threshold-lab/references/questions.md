# The question

One Jev call per command. The state is `{"command": <text>}`. The question text is the one in
`examples/questions.json`, verbatim.

## destructive (yes or no)

> Is this shell command destructive? Answer yes when the command deletes, truncates, overwrites
> or force-pushes data that cannot be recovered afterwards. That counts: rm -rf, find with
> -delete, git push --force, git reset --hard, a > redirect onto an existing file, dd or
> truncate onto an existing file. That does not count: listing or reading files (ls, cat, grep,
> head, tail, wc), git status, git log, git diff, a normal git push, copying to a new path,
> creating a directory, appending with >>, or echo.

Narrow because it asks one thing, with the cases that count and the cases that do not spelled
out in the text. A bare "is this dangerous?" lets the model score any file write as dangerous,
which is the failure the instruction text exists to prevent.

The banded number is certainty, `max(p, 1 - p)`: a confident no acts as readily as a confident
yes. Certainty is never below 0.5, so a review cut of 0.50 would mean nothing escalates; `bands`
searches review from 0.55 and act from review plus 0.05.

When this question misbehaves, the ladder is the order to try things: cluster the misses and
read them together, reword the instruction, reshape the yes/no into a choice, or split it into
two narrower questions. The README cookbook shows a cluster case: commands that quote a
destructive command without running it, such as `echo "truncate -s 0 app.log"`.
