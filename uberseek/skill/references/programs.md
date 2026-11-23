# Writing programs

A program is a short piece of Python that runs in a sandbox. The library's functions are already defined
in it. It can compute as much as it likes; only the value of its last expression comes back, plus anything
it printed and the pictures of any looks it made.

## Shape of a good program

```python
hits = find("interview.mp4", "slept in the cave", limit=20)          # search
kept = []
for hit in hits:                                                      # measure and filter, in the program
    quiet = pauses("interview.mp4", hit["start"] - 2, hit["end"] + 2)
    if len(shots("interview.mp4", hit["start"], hit["end"])) == 1:
        kept.append({"start": hit["start"], "end": hit["end"], "text": hit["text"], "pauses": len(quiet)})
kept = kept[:3]
for c in kept:                                                        # look at the few that remain
    observe("interview.mp4", c["start"] - 1, c["end"] + 1, "delivery", "which take is cleanest?")
kept                                                                  # return something small
```

- **Do the narrowing inside the program.** Twenty candidates and their measurements never need to reach
  you; three do.
- **End with a small value.** A list of a few dicts, a count, a span. Not every word of an interview.
- **Look last, and at few things.** A program may look at most 4 times. Decide what deserves a look from
  the measurements, look, return, then decide the next step from the pictures.
- **A program cannot see.** `observe` returns `{"id", "text"}`. Do not branch on what the picture shows:
  the program has no way to know.

## Limits

| Limit | Value | When you hit it |
| --- | --- | --- |
| Running time | 20 seconds of the program's own work (time inside library calls does not count) | Loop over less |
| Memory | 64 MB | Keep less in lists |
| Library calls | 200 per program | Ask for wider spans, fewer times |
| Looks | 4 per program | Return, see the pictures, then look again |
| Result size | 6,000 characters | Return the top few items or a count |
| Printed text | 2,000 characters | Print less |

## The Python that works

Works: variables, numbers, strings and f-strings, lists, dicts, tuples, sets, slices, comprehensions,
`for` and `while`, `if`, functions and `lambda`, `sorted`, `min`, `max`, `sum`, `len`, `range`,
`enumerate`, `zip`, `round`, `abs`, `try` and `except`, `print`, and `import math`, `import json`,
`import re`.

Does not work, and what to do instead:

| This fails | Because | Do this |
| --- | --- | --- |
| `class Clip(Base): ...` | No class inheritance | Use dicts |
| `def gen(): yield x` | No generators | Build a list |
| `import numpy` | No third-party modules | Use `sum`, `sorted`, `math` |
| `open("notes.txt")` | No files | Return the value |
| `import socket`, `import subprocess` | No network, no processes | Not available |
| `await find(...)` | The functions are plain calls | `find(...)` |

## When a program fails

You get the error with the line that caused it:

```
The program failed.
Traceback (most recent call last):
  File "<python-input-0>", line 2, in <module>
    found = cuts("clip.mp4", 5, 2)
ValueError: the span ends (2) before it starts (5)
```

Read the last line, fix that line, run again. A library call that cannot be served raises `ValueError`
with a message that says what to change: a video name that does not exist lists the ones that do. You can
catch it in the program with `try` and `except ValueError`.

## Times and spans

Times are seconds as numbers. A span is a list `[start, end]`.

```python
span = expand([10, 14], before=2, after=3)        # [8, 17]
merge([[1, 2], [1.5, 3], [5, 6]], gap=0.5)        # [[1, 3], [5, 6]]
minus([0, 10], [[2, 3], [5, 12]])                 # [[0, 2], [3, 5]]: what is left of the first span
```
