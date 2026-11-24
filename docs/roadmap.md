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

[AgenticVBench](https://github.com/PhiloLabs/agentic-vbench) is a benchmark of 100 video-editing tasks for
coding agents, built with industry editors. An agent gets source media, a brief and 30 minutes, edits with its
own shell and FFmpeg, and is scored on the file it delivers.

| Category | Tasks | What it needs | How UberSeek fits |
| --- | --- | --- | --- |
| Repurpose | 36 | Find the right moments in sources of minutes to hours, and cut them | The closest fit: locating, selecting and working within a budget |
| Repair | 18 | Find the damaged stretch, then fix it | Half a fit: it helps find the stretch, not repair it |
| Assembly and Sequencing | 46 | Match and order shots by what they show | Needs comparing pictures; there is no search by picture yet |

Why this benchmark: its own failure analysis points at what UberSeek is for. 83% of failed Repurpose runs
spent their time transcribing or thumbnailing whole sources and never assembled a cut, and 65% of failed
Repair runs picked the wrong stretch of time.

**Nothing has been run on it yet.** What it takes:

1. **An adapter.** The benchmark runs agents through Harbor and has no supported way to add a tool. The route
   is a custom agent that installs UberSeek and its skill before the clock starts, leaving the tasks untouched.
2. **Preparation inside the clock.** The rules do not address preparing data beforehand, and the benchmark's
   own ablations show that handing an agent notes lifts scores. So everything UberSeek prepares must happen
   inside the 30 minutes: transcribe a span, not a three-hour source.
3. **State that survives.** The coding agent's host shortens its context. The brief and the notes live in a
   working file the agent re-reads.
4. **A first comparison.** The same agent and model with and without UberSeek, on the Repurpose tasks.

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
