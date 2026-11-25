# Backlog

The work still to do, in order. The [roadmap](./roadmap) says where the project is going; this page says what
comes next and how we will know each item is finished.

## How items get here

- **From use.** Whenever an agent, or we, leave UberSeek and write FFmpeg by hand, or an UberSeek call fails,
  that run adds an item. The run is named in **From**, so the gap can be seen again.
- **Each item has a check.** **Done when** names a test, an eval or a benchmark run that passes. An item
  without one is not ready to start.
- **Measured before built on.** An item that adds an operation is followed by a run that shows whether it is
  used. An item that should raise a score names the score.
- **Finished items move** to the roadmap's "What real use asked for, and got", with what the check showed.

Size: S is under a day, M a few days, L a week or more.

## Now

| # | Item | From | Done when | Size |
| --- | --- | --- | --- | --- |
| 1 | **A harder hook eval**: more strips, some fading in, a distractor moving in part of the frame, a one-frame tolerance | Hook eval 2026-11-25: both conditions scored 1.0, so it cannot tell them apart | Without UberSeek scores below 1.0 on a cheap model, and the reference solution still scores 1.0 | S |
| 2 | **Three runs per cell** on the nine benchmark tasks and the hook eval | Every pilot so far: one run per cell, differences within chance | A results table with three runs per cell, mean and spread | S |
| 3 | **Cuts in the task's own format**: `clip` writes to a path given, keeps the source's frame rate and codec settings; `export` gives cuts in frames or milliseconds | Frozen-frames task: `freezes` found both stretches, the agent cut by hand and failed the picture check. Passage tasks: cuts converted by hand | The frozen-frames task passes in a run that uses `clip`; a test writes and reads both formats | M |
| 4 | **Edges in a pause**: an operation or recipe that moves a chosen edge to the nearest pause or gap, and says how far it moved | Passage-cut tasks: three of four runs found the passage and missed an edge by 0.06 to 0.16 s beyond the tolerance | A test on generated speech; one passage-cut task passes in a run that uses it | M |

## Next

| # | Item | From | Done when | Size |
| --- | --- | --- | --- | --- |
| 5 | **More Sequencing and Assembly tasks**: ten of each, both conditions | Four tried; `overview` is now used in all of them, its effect unknown | A results table over twenty tasks | S |
| 6 | **Story order across a join**: a recipe that checks a proposed order pair by pair with `seam`, and a measure of sound continuity across a join | Sequencing runs: `seam` never used, orders near chance | `seam` used in Sequencing runs; ordering score compared with item 5 | M |
| 7 | **Slow changes**: `events` reports a wipe or fade as one event with its start and end | The reel's closing bars, not reported | A test on a generated fade and wipe | M |
| 8 | **`gaps` and `repeats` on real speech** | Tested only on words written by hand | Both run on the stumble tasks and the interview footage, with what they found recorded | S |
| 9 | **A stronger model** on the same tasks | Only a cheap model tried | One stronger model, both conditions, on the tasks of items 1 and 2 | S |

## With UberScene

| # | Item | From | Done when | Size |
| --- | --- | --- | --- | --- |
| 10 | **Selections into an UberScene file**: what `mark` saved becomes the clips of an edit | The split agreed: UberSeek finds and checks, UberScene builds | An UberScene file made from selections renders, and `verify` passes on the render | M |
| 11 | **Rebuild the reel's hook** in UberScene from the measured timings | Taking the reel apart | The hook eval run on the rebuild gives the reference's timings within one frame | M |
| 12 | **One Repurpose task** end to end | Repurpose is 36 of 100 tasks and needs more than hard cuts | It runs and is scored; needs Anthropic and Gemini keys for the benchmark's judges | L |
| 13 | **A cut-out of a subject** (a person mask) | The reel's subject stays in front of the collage | An UberScene clip with a subject over a changed background | L |

## Later

| # | Item | From | Done when | Size |
| --- | --- | --- | --- | --- |
| 14 | **The Understanding family**: three tasks on long video | The closest fit; strongest agents score under 0.1 | Three tasks run in both conditions | L |
| 15 | **Runs inside Harbor**, so scores compare with published ones | Our runner is not Harbor | One task scored the same in both | M |
| 16 | **A TypeScript or MCP version** to embed in OpenCode and T3 | Raised, not decided | A decision written into the design | S |
| 17 | **The explorer as code and as plain tools** on confirmed tasks (E6), then **comparing candidates against a brief** (M2) | The design's central question | See the design, section 6 | L |
| 18 | **Labels checked by a person** for the 21 locate tasks | Three of five draft labels tried were wrong | Every task has `verified = true` | M |

## Keeping it honest

- Results go in `bench/*/results/` with the note of what was run; this page links the finding, not the numbers.
- A finding from one run is written as one run.
- If an item's check cannot be built, the item is rewritten until it can.
