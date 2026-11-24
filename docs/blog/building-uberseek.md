---
title: What we learned building a shell for video
date: 2026-11-24
summary: Everything so far in one place. Models read UberSeek's pictures correctly; code and plain tools were equally accurate; two small models built a checked clip from one sentence; dropping pictures after one step cut input tokens by a quarter to a third; and on a first benchmark run UberSeek made agents faster but not more often right.
sidebar: false
---

# What we learned building a shell for video

<p class="post-meta">24 November 2026</p>

UberSeek is a way for an AI agent to work inside a video without drowning in it. A video is far larger than
what the agent's next decision needs, so UberSeek lets it narrow things down with code and look only where a
judgment needs eyes. It works like a shell: `find` is `grep`, `observe` is `cat`, and a short program ties
them together.

This post collects what we built and measured over the first two weeks, in the order we learned it, with the
numbers and with what went wrong.

## What an agent can do

| Step | How |
| --- | --- |
| Find where something is said | `find` searches the transcript and returns candidate spans |
| See a span | `observe` returns one picture: numbered frames, the words under them, the sound drawn as a strip |
| See many places at once | `sheet` puts up to 24 frames from anywhere in the video on one picture |
| Combine all of that | A short Python program, run in a sandbox, that returns only what the agent needs next |
| Save a choice | `mark` records a span, snapped to frames, with the looks it rests on |
| Cut and check | `clip` joins selections frame-exactly; `verify` checks the file by code |
| Keep track | `brief`, `note` and a working file hold the task and what was concluded |

## 1. Can a model read the pictures? {#reading}

Every look is one picture: numbered frames in time order, each with its time printed in a corner, and the
sound drawn as a strip underneath with silences shaded. Everything else rests on the model reading that
picture correctly, so we checked that first.

We generated clips whose contents are known from how they were built: a square appears at a known instant,
the tone is silent over a known stretch, there is one cut at a known time. Then we asked questions a program
can check against the log of what was shown. Claude Sonnet 5.5 and GPT 5.6 Terra, three repeats each.

| Question | What it tests | Claude | GPT |
| --- | --- | --- | --- |
| The first picture that shows the square | Reading the grid in time order | 12/12 | 12/12 |
| The time printed on picture N | Reading the labels | 12/12 | 12/12 |
| The pictures the scene changes between | Comparing neighbours | 12/12 | 12/12 |
| The pictures whose tick is inside the silence | Reading the sound strip | 12/12 | 12/12 |
| The picture at the marked instant | The boundary view | 12/12 | 12/12 |

Those are the final numbers. The first run of the scene-change question went differently. We had asked for
"the two consecutive frames" the scene changes between, and GPT scored 0 out of 12, with answers like 117 and
118. It had found the cut and converted it to frame numbers of the video at 30 frames a second. "Frame" meant
a picture on the sheet to us and a frame of the video to the model. The text that comes with every look now
says that a number means a picture on the sheet. That sentence is in the product, not just in the test.

We also asked, on real footage, which picture is on screen when a given word is said, with the words shown in
the text, under the pictures, or both. All three were read correctly (24 of 24 each); text only was the
cheapest. A lookup of one word does not test a judgment that needs word and picture together, so this stays
open.

Generated clips are clean: large shapes, one cut, one silence. Twenty questions and two models are enough to
catch a broken format, not to rank models.

## 2. Code against plain tools {#code-or-tools}

UberSeek offers its operations two ways. On the code surface the agent writes a short Python program that
searches, measures and filters in a sandbox and returns a small result. On the tools surface it calls one
operation at a time and reads each result.

We ran six tasks of the form "find A, then the related B": the longest pause after a word, the shot after the
shot in which a word is said, how many times a word is said inside the longest shot. A reference program
computed each answer from the same data the agent can reach. Claude Sonnet 5.5, both surfaces, three
repeats: 36 runs.

**Accuracy was equal.** On the four sound tasks both surfaces were right 12 times out of 12.

**Code was cheaper where there was much data, and dearer where there was little.**

| Task | Code: input tokens | Tools: input tokens |
| --- | --- | --- |
| Count a word inside the longest shot | 29,045 | 89,402 |
| The next "robotic" after "crane" | 27,687 | 37,101 |
| Longest pause after a word | 32,264 | 24,132 |
| The shot after the shot with a word | 29,001 | 16,676 |
| Mean | 29,499 | 41,827 |

The model did combine steps: 22 of its 44 programs used two or more operations. Two smaller models, in an
earlier trial, never did, until the skill showed them worked examples.

**The finding we did not expect.** Two of the six "correct" answers were wrong. One task asked for the
longest silence, and the detector had recorded one silence of 4.4 seconds as two that touch. Our reference
program took the longest entry in the list, and so did every program the model wrote: all three matched the
reference, and all three were wrong about the footage. On the tools surface the model read the list, saw two
silences meeting at the same instant, joined them, and was right all three times. The other flawed task was
the same story with a missed cut.

A program trusts its data. A model that sees the data can notice it is wrong. Code keeps the data out of the
model's context, which is where the saving comes from, and also why the error went unseen. So we fixed the
measurement (silences that touch are one silence), added a rule to the skill (return the runner-up as well as
the winner, and look at the winner before reporting it), and kept both surfaces.

## 3. From a request to a checked clip {#clip}

Next the loop was closed: from one sentence to a video file that has been checked. We gave two small models
one request on a 19-minute NASA interview:

> Make a clip of about 15 seconds of her answer about how many nights they slept in the cave.

| | Claude Haiku 5.5 | GPT 5.6 Luna |
| --- | --- | --- |
| Clip length | 15.3 s | 14.5 s |
| Holds the answer | Yes | Yes |
| Passed `verify` | Yes | Yes |
| Looked at both edges before marking | Yes | Yes |
| Looked at its own clip | Yes | Yes |
| Input tokens | 132,906 | 169,666 |

Both found the answer in the transcript, looked at the candidate, set the edges on pauses, looked at both
edges, cut, checked, and then looked at the result.

`verify` checks that the file decodes, holds exactly the frames that were selected, and that each part starts
and ends on the frame that was chosen. Re-encoding changes pixels a little, so it asks that the frame look
like the one chosen, and no less like it than like the frame before or after. A test confirms it catches a cut
one frame off. It does not say the clip is good: nobody judged these two clips, and whether the cuts sound
clean is open.

## 4. Pictures that stay one step {#context}

That clip took 130,000 to 220,000 input tokens, four to six times what locating a moment takes. Most of it
was pictures: each look returned an image, the image stayed in the conversation, and it was sent again with
every request that followed.

A study of agent harnesses asked when dropping old context changes whether an agent succeeds
([arXiv:2610.26632](https://arxiv.org/abs/2610.26632)). Dropping a fact that can be looked up again cost
nothing; dropping one that cannot be recovered took success down to chance. For video this gives a rule. A
picture can always be shown again: it is stored under its id. What the agent concluded from it cannot be
recovered unless it was written down. So pictures go, and notes stay.

A picture is now sent once, in the request right after the look, then replaced by its id and its note. The
look says so ("This picture leaves your context after your next step. Keep what you conclude from it."), and
`note(id, text)` records the conclusion in a working file rewritten after every step. The same clip request,
one run per setting:

| Setting | Claude Haiku 5.5 | GPT 5.6 Luna | Notes written |
| --- | --- | --- | --- |
| Pictures stay for good | 217,515 input tokens | 137,063 | 1 / 1 |
| Pictures stay one step | 163,089 | 90,488 | 3 / 5 |
| The same, with provider caching | 146,473, of which 101,103 from cache | 134,491, of which 101,182 from cache | 3 / 5 |

Input tokens fell 25% and 34%, and every clip still held the answer and passed the checks. The models wrote
more notes once they were told the picture would not stay. With caching, about 70% of input tokens became
cache reads, and a run cost roughly 60% less than at the start. Token counts vary by tens of thousands
between runs of the same setting, so the direction is clear and the exact percentages are not.

The other half is rules. Two studies found that when an agent's context is summarised to make room, the
summary silently drops about a third of a task's constraints
([arXiv:2610.31778](https://arxiv.org/html/2610.31778), [arXiv:2608.22752](https://arxiv.org/abs/2608.22752)).
So the task is recorded word for word with `brief` and kept at the top of the working file. An agent whose
context was shortened reads that file and carries on.

## 5. A first run on a public benchmark {#benchmark}

Our own tasks were written by us. [AgenticVBench](https://github.com/PhiloLabs/agentic-vbench) is not: 100
video-editing tasks, each with a 30-minute clock, inputs in a folder, and a verifier that fetches the answer
only after the agent has finished. We took five Repair tasks that need finding a place in a video, and ran
each once with and once without UberSeek: OpenCode as the agent, Claude Haiku 5.5 as the model, the task's
own image, limits and verifier, in our own runner rather than the benchmark's harness. The task's reference
solution scores 1.0 through it.

| Task | Without UberSeek | With UberSeek | Tolerance |
| --- | --- | --- | --- |
| Remove a passage (tech review) | 0 · edges off by 0.16 s, 0.03 s · 770 s | 0 · edges off by 0.16 s, 0.08 s · 119 s | 0.1 s |
| Remove a passage (news report) | 0 · edges off by 0.11 s, 7.0 s · 387 s | 0 · edges off by 0.36 s, 0.10 s · 81 s | 0.2 s |
| Remove duplicated frames | 0 · both cuts found, output failed the picture check · 225 s | 1 · 207 s, UberSeek not used | 0.2 s |
| Remove a stumble (interview) | 0 · wrong place, 12.8 s away · 346 s | 0 · wrong place, 12.8 s away · 88 s | 0.1 s |
| Put two swapped shots back | 0 · no output, asked for a hint · 507 s | 0 · no output, asked for a hint · 203 s | |

The ten runs cost about $0.15 together.

- **No difference in score that UberSeek can claim.** The one pass came from a run that did not use it.
- **Near misses decide the score.** Three of the four passage runs found the right passage and missed one
  edge by 0.06 to 0.16 s more than allowed. The verifier is all or nothing per cut.
- **With UberSeek the agent finished faster on all five tasks**, mostly because the transcript was ready
  instead of installed and scripted by hand.
- **The agent used UberSeek without being told to** on three tasks, 8 to 12 commands each, and not at all on
  the duplicated-frames task, where no operation fits.
- **On the swap task both runs stopped to ask a question** that nobody answers in a benchmark run.

One run per cell on five tasks is an observation to act on, not a measurement.

## What is next

- **Edges.** Word times from a small speech model are too coarse for a 0.1-second tolerance. A cut's edge
  should snap to the nearest pause, and the skill should say so.
- **Duplicated and repeated frames** need an operation of their own.
- **Repeats.** Three runs per cell on more tasks before reading any difference.
- **The fixed cost.** The skill and the tool definitions are about 6,700 tokens sent with every request.
  Caching makes them cheap; it does not make them fewer.

## What does not work yet

- **Hard cuts only.** No transitions, captions, speed changes or music.
- **The agent cannot hear.** Sound reaches it as measurements and as a drawn strip. A click or a clipped
  breath at a cut is invisible to it, and to `verify`.
- **`find` matches words, not meaning.** A paraphrase finds nothing, and something shown but not said has to
  be found by looking.

The code, 137 tests and every result file are at
[github.com/prefix-tree/uberseek](https://github.com/prefix-tree/uberseek). To try it, see
[Get started](../get-started).
