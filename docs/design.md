# UberLens: design

UberLens is two things:

1. **A harness** that lets a general agent (Claude Code, Codex, any tool-calling model) **explore** video and
   **edit** it. It gives the agent ways to look only where it matters, remembers what was seen and in which version
   of which file, makes edits through [UberScene](https://github.com/prefix-tree/uberscene), and checks the rendered
   result before calling it done.
2. **A benchmark** that measures how well an agent explores and edits, with and without the harness, on footage
   that can be redistributed.

UberLens trains no model. It is tools, state, prompts and checks around a model you choose.

Status: design, second version. It replaces the first draft, which described a question-answering agent with
streaming and training. Every choice below names its source or is marked **ours**; the research behind it is in
[research.md](research.md) (perception), [research-editing.md](research-editing.md) (editing),
[research-importance.md](research-importance.md) (what to look at) and [activity-prior.md](activity-prior.md).
Where those documents list changes to "design.md", they mean the first draft; this version takes them in or
defers them to section 11.

## 1. Why this shape

- **A harness is where the evidence is.** VIVID added about 20 points on AgenticVBench to the same model with no
  training (58.6 vs 38.4 for Codex), and its ablation ranks what matters: looking on demand (−16.0 without it),
  reviewing the output (−14.6), version-pinned memory (−10.8). The perception papers (ForeSeek, OmniAgent,
  ActiveForager) get their gains from fine-tuning and reinforcement learning, and ForeSeek's own ablation says its
  predict-then-verify loop only pays off after training.
- **Agents fail by drowning.** On AgenticVBench, 83% of failed repurposing tasks spent the budget transcribing or
  thumbnailing the whole source and never assembled an edit; 65% of failed repairs looked in the wrong time window.
  The harness's job is to make the cheap, targeted look the easy path.
- **UberScene removes the hard half.** The editing papers build their machinery on FFmpeg commands. In UberScene the
  edit is one TSX file changed through typed, validated, undoable actions, with lint, layout checks, labelled
  contact sheets and a per-frame render cache. UberLens uses these instead of rebuilding them.
- **No benchmark fits.** Every public video benchmark is non-commercial and none may redistribute its videos; none
  measures exploring and editing together, or what a harness adds at equal cost.

## 2. Scope

| | In the first version | Later (section 11) | Not planned |
| --- | --- | --- | --- |
| Explore | Recorded video: find moments, answer with evidence | Live streams | |
| Edit | Timeline edits through UberScene: cut, trim, order, captions, titles, sound | | Generative pixel edits |
| Models | Any hosted or local tool-calling model, as configuration | A trained fast decision model; fine-tuning | |
| Memory | Evidence store, working files, coverage | Event graph, story importance | |

## 3. Parts

```
                agent (your model)                         benchmark runner
                       │ tools (MCP / CLI / skill)                │
┌──────────────────────┴──────────────────────────────────────────┴─────────┐
│ UberLens                                                                  │
│  explore: catalog · overview · inspect · listen · transcribe · retrieve   │
│  edit:    actions · apply · undo · check · look · review                  │
│  state:   versions · evidence · working files · coverage · budget · log   │
│  prior:   activity profile (bitrate, keyframes, audio), shots             │
└───────────────┬───────────────────────────────────┬───────────────────────┘
                │ ffprobe / PyAV / Whisper          │ uberscene CLI
            source media                       video.tsx → render
```

The harness ships as an MCP server, a CLI and an agent skill, as VIVID does, so it works with an agent the user
already has. The benchmark drives the same tools.

## 4. State

All state lives outside the model's context, in the project folder (`.uberlens/`), so it survives a full context
and a new session.

**Versions** (VIVID). Every media file has `asset_id = "asset_" + sha256(relative path + "\0" + sha256(content))[:24]`.
A rewritten file is a new version; nothing is ever silently reattached to a newer one. A render has
`render_id = hash(TSX text, media content hashes, props, UberScene version, Chrome version)`, computed before
rendering (**ours**; it relies on renders being deterministic, which M0 tests).

**Evidence** (VIVID, OmniAgent). Each observation is a row:

```python
class Evidence(BaseModel):
    evidence_id: str                 # "ev_" + 24 hex
    version: str                     # asset_id, or render_id + frame-cache key for rendered frames
    kind: Literal["frames", "audio", "transcript", "check", "critique"]
    span: Span                       # seconds in that version
    anchors: list[str] = []          # media terms that survive trims: "word:12", "shot:3"  (ours)
    timestamps: list[float]          # the frames actually decoded
    crop: tuple[int, int, int, int] | None
    text: str                        # what the model wrote about it: a hypothesis until confirmed
    expected: str | None             # what the model said it expected to see, before the look
    verdict: Literal["confirmed", "partial", "not_found"] | None   # required when `expected` is set
    confirmed_by: list[str] = []     # evidence ids of a second modality or a denser look  (ours)
    provenance: Literal["observed", "index"]   # index entries guide, never confirm  (ours)
```

Two rules are enforced by the store, not left to the prompt (**ours**):

- A look made with an expectation cannot be saved without a verdict (ForeSeek's three verdicts).
- `text` is the model's caption of its own look. `retrieve` returns it marked unconfirmed until `confirmed_by`
  names a second look: another modality, or the same one narrower or denser.

Rows go in SQLite with the images stored by content hash. Old media leaves the context after each step and a
one-line stub with the evidence id and timestamps stays (OmniAgent). Evidence about a rendered frame is pinned to
UberScene's frame-cache key, so a finding about scene 3 stays valid after an edit to scene 5 and expires exactly
when its frame changes (**ours**).

**Working files** (VIVID): `TASK.md` (the brief), `PLAN.md` (the current plan, size-capped), and a generated index
of the evidence. An agent that runs out of context writes a checkpoint and continues in a fresh one; the budget
carries over.

**Coverage** (**ours**). For each source, which spans have been looked at, with what instrument and at what
density. It answers "have we looked here, and how closely?", and it is always on.

**Belief labels** (ForeSeek), behind a flag, off by default. On top of coverage: `high | medium | low | eliminated`
per interval, with a short hint, and a scheduler that ranks them. This is ForeSeek's trained loop run on an
untrained model, so it is an experiment (section 8.5), not the method.

**Budget and log.** Frames sent to the model, tool calls, model calls, tokens, cost and wall time are counted and
capped. Scorer passes (any embedding or rating model) are counted separately from frames sent to the main model.
Every tool call and decision is logged; the log is the replayable trace and the benchmark's cost record.

## 5. Explore

### 5.1 The method

> Look little, look on purpose, remember exactly what was looked at, and refuse to treat a caption or a busy
> moment as the event.

Understanding here means the claim would have failed if the look had gone the other way. The method has three
layers. A and B ship in M1 and are not optional. C has a simple default; anything heavier is an experiment.

| Layer | What it is | Status |
| --- | --- | --- |
| **A. Instruments** | Ways to look: overview, frames, crop, burst, sound, words | M1 |
| **B. Honesty** | Every look is recorded with its version, timestamps, expectation and verdict; claims cite looks | M1 |
| **C. Search policy** | Which look comes next. Default: narrow and change one thing. ForeSeek's belief scheduler behind a flag | Default in M1, flag measured in M4 |

Activity signals, shots, interval labels and any index are **priors**: they say where to look. Only a look
confirms anything.

### 5.2 Build once per source

Cheap layers computed when a file is first cataloged, cached by `asset_id`, reused by every later question or
edit:

- **Activity profile** ([activity-prior.md](activity-prior.md), **ours**): bitrate, keyframes and audio energy per
  second, with reliability checks. Measured cost: 0.07 s per minute of video for the container signals.
- **Shots and silences**: from UberScene's manifest when the footage is in an UberScene project; otherwise cuts from
  the activity profile.
- **The uniform half of the first look**: the evenly spaced overview frames, which do not depend on the question.

A transcript is **not** built up front. Full-source transcription first is the top failure on AgenticVBench.

### 5.3 Layer A: instruments

| Tool | Does | Limits | Source |
| --- | --- | --- | --- |
| `catalog` | Lists sources with duration, streams, versions, what is cached | | VIVID |
| `overview(source, profile)` | First look, **per question**: ForeSeek's N(T) = clip(round(10 + 3·log2(1 + T/600)), 10, 20) frames as contact sheets of 8 with timestamps. Half are the cached uniform frames; half are placed by the activity profile under `profile` | `profile` is required | ForeSeek, **ours** |
| `inspect(source, span, n, roi)` | Frames spread over a span, optional crop | ≤ 24 frames, span ≤ 600 s; a larger request returns a bounded window and the next request | VIVID, OmniAgent |
| `inspect(..., density="burst")` | A short run at up to native frame rate, for order, motion and "who handed what" | ≤ 24 frames, span ≤ 8 s, so at least 3 frames per second | OmniAgent `get_clip`, ActiveForager's temporal zoom |
| `listen(source, span)` | Loudness, waveform and spectrogram summary, speech presence | ≤ 120 s | VIVID |
| `transcribe(source, span)` | Local Whisper for a span, word timings; partial results kept | spans, never the whole source by default | VIVID |
| `retrieve(query \| evidence_id)` | Exact lookup by id, text search over evidence, filters by source, time, kind; captions come back marked confirmed or unconfirmed | | VIVID |

**`profile` runs before every overview.** The agent picks how the activity half is placed for this question:
`motion` (events and actions), `speech`, `cuts` (scene or topic changes), or `off` (static details such as a sign
or a face: all frames uniform). Models lock onto the most visually striking scene (NEST), and an activity-guided
skim makes that worse for a static-detail question, so there is no default: the choice is made and logged each
time. The uniform half is always kept.

**Why burst exists.** `inspect` at its widest is 24 frames over 600 s, one frame per 25 s. That finds a scene; it
cannot show an event inside it. Every look returns its frame spacing, so the agent and the log can see whether a
look could have caught what it was looking for.

Every instrument returns the timestamps actually decoded, the version, the crop and an evidence id.

### 5.4 Layer B: honesty

- **Every look is a row** in the evidence store (section 4). Pixels and audio leave the context; the row stays.
- **Say what you expect, record what you got.** A look can carry an expectation; if it does, the store requires a
  verdict: confirmed, partial or not found.
- **A caption is a hypothesis.** What the model wrote about a look is unconfirmed until a second look agrees:
  another modality, or the same one narrower or denser.
- **A claim cites its looks.** A claim without an evidence id is a guess and is reported as one. Citing is not
  enough: the cited looks must cover the claim (the right span, at a density that could show it). The benchmark
  scores exactly this (section 8.2).
- **A miss is not absence.** "Not found" means unknown in this sample, at this density. Sampled frames are not
  continuous coverage; a transcript is not listening (VIVID).
- **Priors never confirm.** Activity peaks, shot lists, interval labels and index entries cannot be cited as
  evidence.

### 5.5 Layer C: search policy

The default is the simplest search that works with the instruments, OmniAgent's "scan wide, then bisect" written
out:

1. Choose the profile and run the overview, once per question.
2. Pick the smallest span the question and the overview together suggest.
3. Look at a density that could catch what is asked: a short span, or a burst for motion and order.
4. If the look does not decide it, change **one** of span, density, crop or modality. Never repeat an identical
   look.
5. Stop when the cited looks cover the claim. Otherwise report what is known and where the gap is.

**Behind a flag: ForeSeek's belief scheduler.** Interval labels, a written prediction for every look, demotion
on a failed prediction, and a split of the timeline into first intervals (APS's penalised split of the activity
curve, re-implemented from the paper). ForeSeek's own ablation shows predict-then-verify paying off only after
reinforcement learning, so on an untrained model this may be overhead. It stays off until the benchmark says
otherwise.

**Choice points are logged, not automated.** Which profile, which span, which instrument, and "is this enough?"
go through `decide()` (section 7).

## 6. Edit

The editor's only way to change a video is UberScene. It never writes FFmpeg commands.

### 6.1 Tools

| Tool | Does | Backed by |
| --- | --- | --- |
| `actions(element)` | The actions this element accepts now, with parameter ranges | UberScene `affordances()` |
| `apply(actions, dry_run)` | Runs typed actions (`clip/trim`, `clip/split`, `caption/update`, …). A dry run answers without changing anything; an action that would break the file is refused | `Executor.can()` / `execute()`, `BREAKS_FILE` |
| `undo(round)` | Reverts a round | `invert`, the patch log |
| `check` | Code checks, no model: lint, structure errors, layout rules, export decodes, duration / aspect / codec against the brief, repeated sources, out-of-range trims | `uberscene lint`, `inspect --json`, `--check-layout`, `ffprobe` |
| `look(segment \| around)` | Labelled contact sheets of the render: each clip's first frame, both sides of every transition, each title; cells carry time, frame and element id; optional sound strip | `uberscene look`, `--around`, `--listen` |
| `review` | Runs the critic (6.3) on what changed | |

Each round is a diff of `video.tsx`, so the history of an edit is readable and reversible.

### 6.2 Loop

```
brief ─► explore ─► plan ─► apply ─► check ─┬─ fails ─► fix (the check says what and where)
                      ▲                     └─ passes ─► look ─► review ─┬─ all segments pass ─► done
                      └──────────── one typed fix per failing segment ◄──┘
```

The agent keeps control of strategy (VIVID): the loop is what the tools and prompt make easy, not a fixed
pipeline. Two things are enforced: `review` refuses to run on a render that fails `check` (CutClaw's gates), and
"done" requires a review of the current `render_id`.

### 6.3 Critic

A separate model call that **watches** the render: the `look` sheets and sound strip for each changed segment,
with that segment's intent from the plan (Auto-Director). EditDuet's critic read only a text shot list, asked for
things its editor could not do, and the editor invented functions to match.

Per segment it returns:

```python
class Critique(BaseModel):
    segment: str
    semantic: int                  # 1–5: does it show what the plan says
    craft: int                     # 1–5: framing, pacing, sound, captions
    failure: Literal["wrong_clip", "plan", "layout", "timing", "ok"]
    keep: list[str]                # what must not regress
    fix: Action | None             # exactly one UberScene action
```

- `fix` must be in `actions(element)` and pass a dry run, or the critique is rejected before the editor sees it
  (**ours**; it removes EditDuet's failure by construction).
- `plan` failures go back to planning; the rest go to the editor (Auto-Director's routing).
- A segment at 4 or more on both scores is frozen. Only frames whose cache key changed are reviewed again
  (**ours**).
- At most 3 rounds (Auto-Director). At the limit the agent returns the best version, with failing segments and
  reasons listed.

## 7. Small decisions

Many choices are picks from a short list: which profile, which span, which instrument, is the evidence enough, which segment
to review. A fast scorer could make them and hand off to the main model when unsure (AnyS1, Gemini Decision 1).
No source has tested this on video decisions, and exploring takes about two rounds per question in ForeSeek, so
the saving is unproven.

First version: one `decide(point, options)` interface that the main model answers, with every decision logged
with its options, including "none of the above". Those logs are what a threshold per decision point would later
be fitted on (20 or more runs, checked on held-out runs). Nothing fast runs until the logs show a saving.

## 8. Benchmark

Working name: **UberLens Bench**. It measures an agent on exploring and editing video, and what a harness adds.

### 8.1 Principles

- **Redistributable footage.** Public-domain and openly licensed sources only (license check per source in M0), so
  the whole benchmark can be downloaded and results reproduced. Benchmark media never goes in this repo; a
  manifest with hashes does.
- **Score the result, not the plan.** Rendered output and cited evidence are scored. HKUDS VideoAgent's headline
  number is a judge rating plans that were never run.
- **Ground truth from code where possible.** Because an UberScene video is a file, defects can be injected by
  known actions and checked exactly (**ours**).
- **Cost is part of the score.** Every result reports frames sent, model calls, scorer passes, tokens, cost and
  time, next to accuracy.

### 8.2 Tasks

| Family | Task | Scored by |
| --- | --- | --- |
| **Find** | "Where does X happen?" in sources from 5 minutes to 2 hours | Overlap of the answered span with the labelled span; whether the cited looks fall inside it at a density that could show the event |
| **Answer** | Questions needing one or several moments, including static details, speech, order and motion | Correctness; **support**: do the cited looks cover the labelled spans; a right answer with wrong or missing support is counted separately; split by question type (event, speech, static detail, order or motion, far-apart moments) |
| **Repair** | An UberScene project with one injected defect (a mistimed cut, a caption off its word, a clipped title, a wrong clip, bad levels) | By code: is the defect gone, and is everything outside the defect window unchanged |
| **Assemble** | A storyboard and a pool of clips with distractors; build the cut | Right clip per slot, order, durations, all by code |
| **Repurpose** | A brief ("60-second vertical teaser from this talk") | Code checks for format; yes/no rubric items for content, judged as in 8.4 |

The first release is small, about 20 tasks per family, so it can be labelled by hand and run cheaply.

### 8.3 What gets compared

- The same model **with and without** the harness (VIVID's protocol). This is the headline number.
- Ablations: uniform first look instead of `overview`'s activity half, no burst, no required verdict, no
  caption confirmation, the belief scheduler on, no evidence store, no `check`, no `review`, and a critic that
  reads the timeline instead of watching the render. No paper has run the last one.
- Reference points: uniform frames into one model call; a transcript-only agent.

### 8.4 Judging

Anything code can decide, code decides. Rubric items use a model judge from a **different family** than the agent
and critic, validated against human grades on a held-out set before its numbers are reported; the agreement is
published with the results.

### 8.5 Questions the first run should answer

1. How many points does the harness add to the same model, on each family, and at what extra cost?
2. Does an activity-guided first look beat a uniform one at the same frame count? (The removal rule is in
   activity-prior.md section 9.)
3. Does ForeSeek's belief scheduler help an untrained model over the default narrow-and-change-one-thing
   search, or is it overhead?
4. How often does the critic approve a bad edit, and does watching beat reading?

### 8.6 External benchmarks

AgenticVBench (editing; the comparison VIVID reports) and LVBench and Video-MME long (exploring). Their media is
research-only and not redistributable, so they are for comparison with published work, never for product claims,
and only through download adapters.

## 9. Code

Python, MPL-2.0. **Decided (2026-11-22):** the harness is written in Python and wraps UberScene through its CLI. A
TypeScript harness calling UberScene's `Executor` directly was considered and not chosen; Python suits the media
tooling and the benchmark.

```
uberlens/
  state/        # versions, evidence store (SQLite + blobs), working files, coverage, budget, log
  media/        # probe (ffprobe / PyAV), frames, audio, transcribe
  prior/        # activity profile, partition, first-look placement
  explore/      # catalog, overview, inspect, listen, transcribe, retrieve
  edit/         # uberscene bridge: actions, apply, undo, check, look; critic
  decide.py     # the decision interface and its log
  server/       # MCP server, CLI, skill
bench/
  tasks/        # manifests: sources (with hashes), briefs, labels, checks
  inject/       # defect injection for Repair
  score/        # per-family scorers, judge, cost report
  run.py        # runs an agent with or without the harness
tests/
```

## 10. Milestones

0. **M0, checks before building.** Render the same UberScene file twice and compare frame hashes; confirm what the
   frame-cache key covers. License check of candidate benchmark footage and of AgenticVBench. Pick the first
   models.
1. **M1, explore.** Versions, evidence store, working files, budget and log; activity profile and partition;
   `catalog`, `overview` with profiles, `inspect` with burst, `listen`, `transcribe`, `retrieve`; coverage; the
   store's verdict and confirmation rules; the default search policy in the prompt; MCP server and CLI. Tests on
   synthetic videos with known events.
2. **M2, edit.** The UberScene bridge, `check`, `look`, the critic with typed fixes, freezing and the round limit.
   Tests on small UberScene projects with injected defects.
3. **M3, benchmark v0.** Find and Repair first (their ground truth is cheapest), then Answer, Assemble,
   Repurpose; the runner and cost report; first numbers with and without the harness.
4. **M4, experiments.** Section 8.5, the ablations, and AgenticVBench for comparison. Decide from the decision
   logs whether a fast scorer is worth building.

## 11. Later

Each is covered in the research docs and waits for the benchmark to show it is needed.

- **Query-aware scan**: FOCUS-style scoring of intervals with a small image-text model, behind a budget gate
  (about 675 scorer passes per video hour for its first stage).
- **Highlight prior for edits**: HiVid-style ratings per second, conditioned on the brief.
- **Lazy narrative index and event graph**: built when one project gets many prompts; entries guide and never
  count as evidence (NEST, Event-Causal RAG).
- **Fast decision model**: thresholds fitted per decision point from the logs.
- **Streaming**: ActiveForager's answer, zoom, recall or wait on a short window, and the activity prior's wake
  triggers. ActiveForager's code has no license, so it would be written from the paper.
- **Training**: fine-tuning on harness traces.

## 12. Licenses

- **Can be ported with notices**: VIVID (MIT), OmniAgent (Apache-2.0), ForeSeek (MIT), Q-Gate (MIT), FOCUS
  (Apache-2.0). UberScene is MIT.
- **Read, copy nothing**: ActiveForager and APS (no license), Crayotter (non-commercial), EditDuet (no code).
- **Avoid**: HKUDS VideoAgent's code (conflicting license signals, bundled non-commercial and GPL tools).
- **Unverified**: licenses of Hugging Face weights and datasets, AgenticVBench's repo and data, CutClaw.

## 13. Open questions

1. Which models first, for the agent, the critic and the judge (the judge must be a different family)?
2. Which footage for the benchmark, and who labels it?
3. Does UberLens also need to edit footage that is not in an UberScene project? If yes, the first step is
   wrapping it in one.
4. The benchmark's name, and whether it lives in this repo or its own.
