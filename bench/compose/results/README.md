# Compositional search on two surfaces: results

Run on 2026-11-24 with Claude Sonnet 5.5 through OpenRouter. Six tasks of the form "find A, then the related
B", the `code` surface against the `tools` surface, three repeats: 36 runs, $2.73. File
`2026-11-24T100749.json`. Both surfaces had the skill and the same cap on what one call may return.

With 18 runs per surface this is indicative, not conclusive.

## What it shows

**1. On the four sound tasks, both surfaces were right every time.** 12 of 12 each. A strong model can find A
and link it to B either way; composition itself was not the hard part.

**2. Code cost fewer tokens overall, but not on every task.**

| Task | Related by | Code: tokens in | Tools: tokens in | Code: requests | Tools: requests |
| --- | --- | --- | --- | --- | --- |
| Count a word inside the longest shot | words and structure | 29,045 | 89,402 | 4.3 | 7.0 |
| The next "robotic" after "crane" | words | 27,687 | 37,101 | 4.7 | 5.3 |
| Longest pause after a word | time | 32,264 | 24,132 | 5.0 | 3.7 |
| The shot after the shot with a word | structure | 29,001 | 16,676 | 4.7 | 3.0 |
| **Mean of these four** | | **29,499** | **41,827** | 4.7 | 4.8 |

Code won where there was a lot of data to go through: counting a word over three minutes of speech took the
tools surface up to nine requests and 120,000 tokens, paging through the words. Code lost on the two tasks
that needed only a couple of lookups, where writing programs was overhead. Requests and wall time were the
same on average.

**3. This model did combine steps.** 22 of its 44 programs used two or more operations. The two cheap models
in the earlier trial never did.

**4. Two of the six tasks were flawed, because their "computed" answers were wrong.** This is the most
useful finding.

- *The longest silence.* The detector had recorded one silence of 4.4 seconds as two that touch. The
  reference took the longest entry in the list and so did every program on the code surface: all three
  matched the reference and all three were wrong about the footage. On the tools surface the model read
  the list, saw two silences meeting at the same instant, joined them, and was right all three times. The
  measurement is fixed (touching silences are now one), and with the corrected reference the score on this
  task is code 0 of 3, tools 3 of 3.
- *The longest shot.* The detector missed a cut, so the "longest shot" holds two. Runs that looked at it
  rejected it and answered with another shot; they were marked wrong against a reference that was wrong.
  The true answer needs a person, so this task is left out.

A program that takes `max()` over a list trusts the list. The model never sees the entries, so it cannot
notice that two of them touch. Plain tools put the data in front of the model, which costs tokens and
catches this kind of error.

## What follows

- **Neither surface should be dropped.** Accuracy is equal; cost depends on how much data the task has.
- **One surface that offers both is the sensible default:** the plain operations, plus `execute` for when a
  task needs more than a few calls or more data than fits in a reply. The skill should say when to use
  which. The full E6 should test that against each alone.
- **Programs should check what they compute on.** The skill's rule "a measured cut can be wrong" needs a
  sibling for programs: return the runner-up as well as the winner, and look at the winner before
  reporting it.
- **A computed answer is not ground truth.** It is only as good as the measurement under it. Tasks built
  this way still need their answers checked against the footage.

## Limits

- One model, six tasks, three repeats.
- The tasks need searching, filtering and linking. They say nothing about judging a picture, which is what
  choosing a moment needs.
