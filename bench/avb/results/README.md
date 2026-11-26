# AgenticVBench pilot

Five Repair tasks from [AgenticVBench](https://github.com/PhiloLabs/agentic-vbench), each run once with and
once without UberSeek. Agent: OpenCode 1.19.6. Model: `anthropic/claude-haiku-5.5` through OpenRouter. Run by
`bench/avb/run.py`, not by Harbor, so these are not leaderboard results. Each run uses the task's base image,
CPU and memory limits and 30-minute clock, and is scored by the task's own verifier.

The task's reference solution scores 1.0 through this runner (`--conditions oracle`).

## Results (2026-11-24, one run per cell)

| Task | Without UberSeek | With UberSeek | Tolerance |
| --- | --- | --- | --- |
| content-cut-mkbhd | 0 · ends off by 0.16 s, 0.03 s · 770 s | 0 · ends off by 0.16 s, 0.08 s · 119 s | 0.1 s |
| content-cut-wsj | 0 · ends off by 0.11 s, 7.0 s · 387 s | 0 · ends off by 0.36 s, 0.10 s · 81 s | 0.2 s |
| glitch-dup-long | 0 · both cuts found; output failed the picture check · 225 s | 1 · 207 s (UberSeek not used) | 0.2 s |
| disfluency-interview-3 | 0 · wrong place (12.8 s away) · 346 s | 0 · wrong place (12.8 s away) · 88 s | 0.1 s |
| swap-car | 0 · no output; asked the user for a hint · 507 s | 0 · no output; asked the user for a hint · 203 s | |

Total cost of all runs, the trial pair included: about $0.15.

## What it shows

- **No difference in score that can be credited to UberSeek.** The one pass came from a run that did not use it.
- **Near misses decide the score.** Four of the six content-cut and glitch failures found the right place and
  missed an edge by 0.03 to 0.26 s more than allowed. The verifier is all or nothing per cut.
- **With UberSeek the agent was faster** on four of five tasks (81 to 203 s against 346 to 770 s), mostly
  because the transcript was ready-made instead of installed and scripted by hand.
- **The agent used UberSeek without being told to** on three tasks (8 to 12 commands: transcript, `find`,
  looks), once on a fourth, and not at all on the glitch task, where it has no operation that fits.
- **On the swap task both runs stopped and asked a question.** Nobody answers in a benchmark run.

One run per cell on five tasks: these are observations to act on, not a measurement.

## What to change next

1. Edges: word times from the `base` Whisper model are too coarse for a 0.1 s tolerance. Snap a cut's edge to
   the nearest pause (`pauses`) and say so in the skill.
2. A line in the instructions that nobody will answer questions, in both conditions.
3. An operation for repeated or duplicated frames, which the glitch tasks need.
4. Three runs per cell before reading any difference.

## Sequencing and Assembly (2026-11-24, one run per cell)

Two tasks of each family, the same agent and model. Both families' reference solutions score 1.0.

| Task | Without UberSeek | With UberSeek |
| --- | --- | --- |
| Sequencing 1 (13 clips) | 0.05 | 0.00 |
| Sequencing 2 (7 clips) | 0.14 | 0.07 |
| Assembly 1 (4 slots from 12 clips) | 0.00 (1 of 4 right) | 0.63 (3 of 4 right) |
| Assembly 2 (4 slots from 12 clips) | 0.63 (3 of 4 right) | 0.63 (3 of 4 right) |

Cost of the eight runs: $0.07.

- **UberSeek was not used in any of the eight runs**, so the two columns measure the same thing and their
  differences are chance. The one attempt was `uberseek videos`, which the skill names as an operation and the
  command line does not have.
- **The agent built its own contact sheets with FFmpeg**: one picture per clip, 7 to 20 pictures read per run,
  then one guess. In one run the pictures carried no clip names and it had to make a labelled grid to tell
  them apart.
- **Ordering is close to chance** (0.00 to 0.14). Both runs said the order was a best guess and did not check
  any join.
- **Building the file is not the problem.** Every output passed the verifier's check that each segment matches
  its source clip, except one segment of one run.

What it asks of UberSeek: operations that take many clips at once. One labelled sheet across all clips, a
view of a join (the end of one clip beside the start of another), and `videos` on the command line.

## The skill rewritten, no new operations (2026-11-24, one run per cell)

The same nine tasks with UberSeek, after two changes: a short card of the skill is loaded into every run and
the whole skill is installed, and every operation is a command.

| Task | UberSeek commands, before | After | Score, before | After |
| --- | --- | --- | --- | --- |
| content-cut-mkbhd | 12 | 36 | 0 | 0 (edges off by 0.16 s, 0.03 s; allowed 0.1 s) |
| content-cut-wsj | 8 | 19 | 0 | 0 (cut half of the passage) |
| glitch-dup-long | 0 | 2 | 1 | 0 (both cuts right; output failed the picture check) |
| disfluency-interview-3 | 1 | 12 | 0 | 0 (1.4 s away; was 12.8 s) |
| swap-car | 10 | 10 | 0 | 0 (no output) |
| Sequencing 1 | 1, failed | 3 | 0.00 | 0.12 |
| Sequencing 2 | 0 | 2 | 0.07 | 0.33 |
| Assembly 1 | 0 | 3 | 0.63 | 0.00 |
| Assembly 2 | 0 | 2 | 0.63 | 0.00 |

Cost of the nine runs: $0.13.

- **The skill change did what it was for:** UberSeek was used in nine of nine runs (four of nine before), and
  on the content-cut task through the whole loop: find, words, pauses, a sheet, boundary looks, mark, clip,
  verify.
- **Scores did not improve.** One run per cell, so single differences are chance in either direction.
- **Use exposed faults in UberSeek itself:**
  - `clip` wrote a file 852 pixels wide from an 854-pixel source with non-square pixels. The task wants the
    source's size.
  - A clip cannot be opened by its name from the command line (`uberseek observe cut1.mp4` fails), so the
    agent could not look at its own join.
  - `mark` takes `--reason` where the other operations take `reason=`, and `clip` takes the name first. The
    agent lost five calls to this.
  - `pauses` found one silence in 90 seconds of speech over music, so "put the edge in a pause" had nothing to
    work with.
  - Twelve separate pictures, one per clip: the agent's context dropped the first ones before it had read the
    last, and it fetched them again.

## The new operations, and a hook eval (2026-11-25, one run per cell)

**The nine tasks again, with what real use asked for** (`events`, `freezes`, `region`, `overview`, `seam`,
`gaps`, `repeats`, the clip fixes). UberSeek was used in nine of nine runs, and the new operations were found:
`overview` in all four Sequencing and Assembly runs, `freezes` on the frozen-frames task, `events`, `change`,
`repeats`, `onsets` and `gaps` on the stumble task. Scores: Assembly 2 at 0.25, Sequencing 0.06 and 0.06,
everything else 0. One run per cell; no change that can be read.

- On the frozen-frames task `freezes` gave both stretches, and the agent then cut with its own `select` filter
  and failed the verifier's picture check. The card now says to remove what `freezes` finds with `mark`,
  `clip` and `verify`.
- One run wrote `None` for an argument it meant to leave out; the command line now accepts it.

**A hook eval** (`bench/avb/tasks/uberseek_hook/`, made by `bench/avb/hook.py`): take a collage hook apart.
Report each strip's first frame and column, the flash, and the title card, to within 0.1 s.
`hook-collage-synthetic` is generated, so its answer is known from how it was made; `hook-collage-reel` is the
real reel, its answer measured with `events` and confirmed by eye. Both reference solutions score 1.0, and a
test checks that `events` alone gives the synthetic answer.

| Task | Without UberSeek | With UberSeek |
| --- | --- | --- |
| hook-collage-synthetic | 1.0 · 46 s · 7 steps | 1.0 · 22 s · 7 steps (first command: `events`) |
| hook-collage-reel | 1.0 · 63 s · 13 steps | 1.0 · 51 s · 9 steps (first command: `events`) |

- **The task can be done, and the model resolves it, with and without UberSeek.** Without it, the agent wrote
  its own frame differencing with NumPy, cropped to the picture area, and got every strip right.
- With UberSeek the agent went to `events` first, as the skill now says, and finished faster in fewer steps.
- So this eval does not separate the two conditions. To make it do so it needs to be harder: more strips,
  some that fade in, distractors, or a tolerance of one frame.

## The hook eval, harder, three runs per cell (2026-11-26)

`hook-collage-hard` adds 60 frames a second, nine strips at uneven gaps, two fades, a ball crossing the frame
throughout, a one-frame flash, and a tolerance of 0.02 s. Building it showed `events` finding four of nine
strips; `events` was rebuilt (a change that stays, 16 by 9 parts) and now finds eight of nine within a frame.

| Task | Without UberSeek: score, seconds | With UberSeek: score, seconds |
| --- | --- | --- |
| hook-collage-hard | 1.0, 1.0, 1.0 · 130, 214, 118 s | 1.0, 1.0, 1.0 · 78, 87, 104 s |
| hook-collage-synthetic | 1.0, 1.0, 1.0 · 63, 39, 45 s | 1.0, 1.0, 1.0 · 45, 26, 33 s |
| hook-collage-reel | 1.0, 1.0, 1.0 · 79, 69, 132 s | 1.0, 1.0, 1.0 · 101, 59, 58 s |

Eighteen runs, $0.18.

- **The harder task still does not separate the conditions.** A cheap model writing NumPy frame differences
  gets every strip within a frame. Generated pictures change in clean steps, which is exactly what simple
  differencing handles.
- **With UberSeek it is faster:** 90 s on average against 154 s on the hard task, at the same cost.
- Where `events` was a frame or two late on a fade, the agent with UberSeek still answered right: it checked.
- What would separate them is real footage: strips of moving video, low contrast between strips, camera
  motion, compression noise. That is the next version of this eval.

Files: `2026-11-24T151044.json` (the ten runs), `2026-11-24T155719.json` (content-cut-wsj without UberSeek,
run again because the first try ended when OpenCode refused a write outside `/workspace`; the runner now
allows it), `2026-11-24T150409.json` (the first trial pair), `2026-11-24T150314.json` (the reference solution), `2026-11-24T214931.json` (Sequencing and
Assembly), `2026-11-24T230315.json` (the skill rewritten), and the files after them (the new operations; the hook eval; three repeats of it).
