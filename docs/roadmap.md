# Roadmap

Where the project stands, what comes next, and what it is aiming at. The reasoning behind each step is in the
[design](./design).

## Milestones

| | Milestone | Status |
| --- | --- | --- |
| M0 | The observation contract: exact frames and sound, a log, and proof that a look can be made again | Done |
| M1 | The environment: cuts, the transcript, the library, the sandboxed executor, the skill | Built. One item left: the explorer run both as code and as plain tools, on confirmed tasks |
| M2 | Comparing candidates against a brief | Not started. This carries the central research question |
| M3 | Comparing boundaries | `mark` exists in a simple form; offering alternatives as an operation does not |
| M4 | Controlled experiments against baselines | Not started |

Built ahead of plan, in their smallest form: cutting and checking a clip, and context management.

## The target: AgenticVBench

[AgenticVBench](https://github.com/PhiloLabs/agentic-vbench) is a benchmark of 100 post-production tasks for
coding agents, built with industry editors. An agent gets source media, a brief and 30 minutes, edits with its
own shell and FFmpeg, and is scored on the file it delivers.

| Category | Tasks | What decides it | How UberSeek fits |
| --- | --- | --- | --- |
| Repurpose | 36 | Choosing the right moments from a long source, cuts that do not land mid-word, a vertical reframe, a title card, music under speech. Mostly judged by models | Finding and choosing moments, and checking the result. The build needs more than hard cuts: that is [UberScene](https://uberscene.prefixtree.xyz/)'s part |
| Sequencing | 28 | Seeing 7 to 13 clips and judging which follows which | Looking across many clips at once, which no operation does yet |
| Assembly | 18 | Judging 12 clips for shot size, angle and camera movement | The same |
| Repair | 18 | Seven tasks need a place found exactly; six need picture restoration; five are sound only | The seven locating tasks |

A fifth family, Understanding (25 tasks on videos of 10 minutes to 5 hours, scored by code), is the closest to
what UberSeek is for. The strongest agents score under 0.1 on it after hours of work, so it is a long-term
target, not a first measurement.

**First pilots are run**, in our own runner, not Harbor, so nothing here compares with published scores. Nine
tasks, one run each, a small model: no gain in score. With the first skill the agent used UberSeek in four of
nine runs; with a short card loaded into every run and every operation a command, in nine of nine. The numbers
are in [Results](./results) and in `bench/avb/results/`.

## What real use has asked for

Each item comes from a run where the agent, or we, left UberSeek and wrote FFmpeg by hand.

| Missing | Where it showed |
| --- | --- |
| **A per-frame change measure**, over the whole frame and over parts of it | Frozen frames in a Repair task. A six-strip collage that builds in under a second, where `cuts` found nothing because each strip changes a sixth of the frame. A single flash frame seen only by luck |
| **Looks that follow change, not the clock** | A look at 14 seconds gave 8 frames 2 seconds apart; everything that mattered happened between the first two |
| **Crop and zoom to a region** | A vertical reel whose picture was the middle third of the frame, and an editor's timeline to read in the lower third |
| **A dense sheet at a chosen rate, with times printed** | The 15-frames-a-second sheet we built by hand to time the strips |
| **Sound onsets or beats** | Whether an edit is cut to the music. `pauses` and `loudness` do not say where hits land |
| **One sheet across many clips, and a view of a join** | Sequencing and Assembly: twelve separate pictures overflowed the agent's context before it had read the last |
| **A pause measure that works under music** | One silence found in 90 seconds of speech over music, so "put the edge in a pause" had nothing to use |
| **`clip` keeps the source's size; a clip opens by its name; one argument style** | A clip came out 852 pixels wide from an 854-pixel source; the agent could not look at its own join; five calls lost to `--reason` against `reason=` |
| **Repeated words** | Finding a stumble: `find` matches words, not a phrase said twice |

The first item serves the most cases, so it comes first; crop and zoom second.

## After that

- **Search by what is shown.** Today `find` searches words. Frames indexed by an image-and-text model would
  serve Assembly and Sequencing, if it proves better than looking.
- **Hearing.** The agent sees sound as a drawing. Real audio, for models that can take it, is the known gap
  for judging delivery and cuts.
- **Improving the harness from its own traces.** Every look, program, selection and clip is logged, which is
  the material that recent work on automatic harness improvement learns from. It needs a baseline and a
  held-out set first.
- **Editing through [UberScene](https://uberscene.prefixtree.xyz/).** Hard cuts are all that exists now.

## What is open

- **Labels.** The locate tasks were written by a model, and three of the five tried were wrong. They need a
  person.
- **Editors.** The central experiment is judged by blind editor preference. Without editors it has no measure.
- **Whether code mode earns its place.** Accuracy was equal in the first test; cost depended on the task.
