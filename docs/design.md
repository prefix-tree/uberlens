# UberLens: design

UberLens is two things:

1. **A harness** that lets a general agent (Claude Code, Codex, any tool-calling model) **explore** video and
   **edit** it. It gives the agent ways to look only where it matters, remembers what was seen and in which version
   of which file, makes edits through [UberScene](https://github.com/prefix-tree/uberscene), and checks the rendered
   result before calling it done.
2. **A benchmark** that measures how well an agent explores and edits, with and without the harness, on footage
   that can be redistributed.

UberLens trains no model. It is tools, state, prompts and checks around a model you choose.

Status: design, third version (after an external review at `28b1378`, folded in below). It replaces the first draft, which described a question-answering agent with
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
- **The core claim is evidence-backed edits.** The link between a moment in the source, the typed edit that uses
  it, and the rendered output that verifies it is what UberLens adds. The first milestone proves that one link on
  real footage (section 10). The activity prior and the belief scheduler are hypotheses tested after it works.
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
                │ ffprobe / PyAV / Whisper          │ uberlens-bridge (JSON, Node)
            source media                      UberScene SDK + CLI
                                               video.tsx → render
```

The harness ships as an MCP server, a CLI and an agent skill, as VIVID does, so it works with an agent the user
already has. The benchmark drives the same tools.

## 4. State

All state lives outside the model's context, in the project folder (`.uberlens/`), so it survives a full context
and a new session.

**Versions** (VIVID). Every media file has `asset_id = "asset_" + sha256(relative path + "\0" + sha256(content))[:24]`.
A rewritten file is a new version; nothing is ever silently reattached to a newer one. A **project revision** is
the hash of `video.tsx` plus the manifest; every edit names the revision it expects (section 6.1). A **render** is
identified by the hash of the output file it produced. Approval attaches to that file, not to inputs predicted to
produce it.

Hashing full files costs time on long sources. It is charged to cold start and reported separately from the cost
of later questions on the same file.

**Observations and claims** (VIVID, OmniAgent; the split is **ours**). The store keeps two kinds of row, because
a versioned frame proves what the system *showed* the model, while a caption is the model's *interpretation* of it.

```python
class Observation(BaseModel):          # what was shown; written by the harness, never by the model
    obs_id: str                        # "ob_" + 24 hex
    version: str                       # asset_id of the source, or the render's file hash
    instrument: Literal["overview", "frames", "burst", "audio", "transcript", "check"]
    requested: Span                    # what was asked for
    pts: list[float]                   # presentation timestamps actually decoded
    max_gap: float                     # largest gap between consecutive samples, seconds
    crop: tuple[int, int, int, int] | None
    anchors: list[str] = []            # media terms that survive trims: "word:12", "shot:3"  (ours)
    note: str                          # the model's description: an interpretation, never ground truth

class Claim(BaseModel):                # what the model asserts; it must cite observations
    claim_id: str
    kind: Literal["read_text", "presence", "order", "spoken_words", "audibility", "location", "absence"]
    text: str
    span: Span
    cites: list[str]                   # obs_ids
    expected: str | None               # stated before the look, when the agent states one
    verdict: Literal["confirmed", "partial", "not_found"] | None   # required when `expected` is set
    provenance: Literal["observed", "index"]
```

**Sufficiency depends on the claim**, not on a count of looks. A second look by the same model can repeat the same
mistake, and one legible crop can settle a sign. The store checks each claim against its kind:

| Claim | Supported when the cited observations include |
| --- | --- |
| `read_text` (a sign, a caption, a label) | A crop where the text is legible |
| `presence` (X is in this shot) | A frame of that shot showing X |
| `order` (A happens before B, who handed what) | A burst covering both, `max_gap` under the event's length |
| `spoken_words` (where a phrase is said) | Word-timed transcript of the span |
| `audibility` (is the line clear under the music) | The actual audio of the span, not only a transcript |
| `location` (when X happens) | An observation inside the span at a gap that could show X |
| `absence` (X does not happen) | Not supportable from samples; reported as "not seen at this coverage" |

A claim that does not meet its row is stored as unsupported and reported as a guess. Pixels and audio leave the
context after each step; a one-line stub with the observation id and timestamps stays (OmniAgent). Rows go in
SQLite, images by content hash.

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
| **B. Honesty** | Every look is an observation (version, decoded timestamps, gaps); every claim cites observations that suffice for its kind | M1 |
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
| `retrieve(query \| id)` | Exact lookup by id, text search over observations and claims, filters by source, time, kind; claims come back marked supported or unsupported | | VIVID |

**`profile` runs before every overview.** The agent picks how the activity half is placed for this question:
`motion` (events and actions), `speech`, `cuts` (scene or topic changes), or `off` (static details such as a sign
or a face: all frames uniform). Models lock onto the most visually striking scene (NEST), and an activity-guided
skim makes that worse for a static-detail question, so there is no default: the choice is made and logged each
time. The uniform half is always kept.

**Why burst exists.** `inspect` at its widest is 24 frames over 600 s, one frame per 25 s. That finds a scene; it
cannot show an event inside it. Every look returns its frame spacing, so the agent and the log can see whether a
look could have caught what it was looking for.

Every instrument returns the presentation timestamps actually decoded, the largest gap between them, the version,
the crop and an observation id. A requested span and frame count can overstate what the model had a chance to
see; the decoded timestamps cannot.

### 5.4 Layer B: honesty

- **Every look is an observation** written by the harness (section 4): version, decoded timestamps, largest gap,
  crop. The model's note on it is an interpretation.
- **Every claim cites observations**, and the citations must suffice for the claim's kind (the table in section
  4). A claim without them is a guess and is reported as one. The benchmark scores the same thing (section 8.2).
- **Say what you expect, record what you got.** A claim made with an expectation requires a verdict: confirmed,
  partial or not found.
- **A miss is not absence.** "Not found" means not seen at this coverage. Sampled frames are not continuous
  coverage; a transcript is not listening (VIVID).
- **Priors never support a claim.** Activity peaks, shot lists, interval labels and index entries cannot be cited.

### 5.5 Layer C: search policy

The default is the simplest search that works with the instruments, OmniAgent's "scan wide, then bisect" written
out:

1. Choose the profile and run the overview, once per question.
2. Pick the smallest span the question and the overview together suggest.
3. Look at a density that could catch what is asked: a short span, or a burst for motion and order.
4. If the look does not decide it, change **one** of span, density, crop or modality. Never repeat an identical
   look.
5. Stop when the claim's citations suffice for its kind. Otherwise report what is known and where the gap is.

**Behind a flag: ForeSeek's belief scheduler.** Interval labels, a written prediction for every look, demotion
on a failed prediction, and a split of the timeline into first intervals (APS's penalised split of the activity
curve, re-implemented from the paper). ForeSeek's own ablation shows predict-then-verify paying off only after
reinforcement learning, so on an untrained model this may be overhead. It stays off until the benchmark says
otherwise.

**Choice points are logged, not automated.** Which profile, which span, which instrument, and "is this enough?"
go through `decide()` (section 7).

## 6. Edit

The editor's only way to change a video is UberScene. It never writes FFmpeg commands.

**The bridge** (**ours**; required by the code). UberScene's CLI only reads (`inspect`, `lint`, `look`, renders);
`affordances()`, `can()`, `execute()` and undo live in its TypeScript SDK, and the `Executor` keeps a patch log
that is written into the TSX as a separate step. So UberLens includes `uberlens-bridge`, a small Node process
backed by the SDK that speaks JSON over stdin/stdout. Python calls it; nothing else in UberLens is TypeScript.
Each mutation carries the project revision it expects and is refused if the file has changed, so a valid action
cannot silently apply to a different cut.

### 6.1 Tools

| Tool | Does | Backed by |
| --- | --- | --- |
| `actions(element)` | The actions this element accepts now, with parameter ranges | bridge → SDK `affordances()` |
| `apply(actions, expected_revision, dry_run)` | Runs typed actions (`clip/trim`, `clip/split`, `caption/update`, …), writes them into `video.tsx`, returns the new revision. A dry run answers without changing anything; an action that would break the file is refused | bridge → `Executor.can()` / `execute()`, `BREAKS_FILE` |
| `undo(round, expected_revision)` | Reverts a round | bridge → `invert`, the patch log |
| `check` | Code checks, no model: lint, structure errors, layout rules, export decodes, duration / aspect / codec against the brief, repeated sources, out-of-range trims | `uberscene lint`, `inspect --json`, `--check-layout`, `ffprobe` |
| `look(segment \| around)` | Labelled contact sheets of the render: each clip's first frame, both sides of every transition, each title; cells carry time, frame and element id; optional loudness and transcript strip | `uberscene look`, `--around`, `--listen` |
| `excerpt(around, seconds)` | A short audiovisual clip of the actual render around an edit, for the critic to watch and hear | ffmpeg on the rendered file |
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
"done" requires a review of the current render file.

### 6.3 Critic

A separate model call that **watches and hears** the render: the `look` sheets and an `excerpt` around each changed
edit, with that segment's intent from the plan (Auto-Director). The `--listen` strip shows levels and words; it
cannot show whether dialogue is intelligible or a cut lands on the beat, so the critic gets real audio. EditDuet's critic read only a text shot list, asked for
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
- Approval is tied to the render file it was given. A frame-cache hit does **not** carry approval forward: an
  unchanged frame can sit beside a different cut, against different narration or under a different mix, and
  UberScene's cache keys media by size and modification time and does not see `--import` code. Frame keys are used
  to reuse images, not verdicts.
- Within a round, a segment at 4 or more on both scores is not reviewed again unless an edit touches it. After any
  timing change, the transitions on both sides of the edit are reviewed again.
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
| **Find → Repair** | A long source and a draft whose cut misses a specific spoken phrase (or another injected defect: a caption off its word, a clipped title, a wrong clip, bad levels). Find the moment, cite the source span, apply a typed fix, render. Includes cases where the phrase is absent and distractors that sound alike, so a confident guess can fail | **Grounded repair success**: an independent verifier finds the phrase and the cut in the rendered output, the cited source span is right, and unrelated edits are preserved. Also: localization error, false completion, wall time, cost |
| **Assemble** | A storyboard and a pool of clips with distractors; build the cut | Right clip per slot, order, durations, all by code |
| **Repurpose** | A brief ("60-second vertical teaser from this talk") | Code checks for format; yes/no rubric items for content, judged as in 8.4 |

About 20 tasks per family is enough to debug the benchmark, not to decide small differences: one task moves a
20-task score by five points. Claims about a few points need more tasks, and results are reported with paired
uncertainty intervals grouped by source video.

### 8.3 What gets compared

Every comparison is at matched budgets.

| Comparison | What it answers |
| --- | --- |
| Native agent vs full UberLens (VIVID's protocol) | Does the whole product improve task completion? |
| Same model and the same UberScene actions, with generic media tools vs UberLens's observation and claim tools | What UberLens's own design adds when both arms can make the same edits |
| Same harness, uniform vs activity-guided first look | Does the activity prior help search at the same first-look budget? |

The second row is the one that matters for the design: if the same model makes more grounded, correct repairs with
the same editing actions and budget, UberLens works, even if uniform sampling beats the activity prior.

- Further ablations: uniform first look instead of `overview`'s activity half, no burst, no required verdict, no
  claim-kind sufficiency, the belief scheduler on, no evidence store, no `check`, no `review`, and a critic that
  reads the timeline instead of watching the render. No paper has run the last one.
- Reference points: uniform frames into one model call; a transcript-only agent.

### 8.4 Judging

Anything code can decide, code decides. Rubric items use a model judge from a **different family** than the agent
and critic, validated against human grades on a held-out set before its numbers are reported; the agreement is
published with the results.

### 8.5 Questions the first run should answer

1. How many points does the harness add to the same model, on each family, and at what extra cost?
2. Does an activity-guided first look beat a uniform one at the same frame count, on the same footage re-encoded
   several ways? (activity-prior.md section 9.)
3. Does ForeSeek's belief scheduler help an untrained model over the default narrow-and-change-one-thing
   search, or is it overhead?
4. How often does the critic approve a bad edit, and does watching beat reading?

### 8.6 External benchmarks

AgenticVBench (editing; the comparison VIVID reports) and LVBench and Video-MME long (exploring). Their media is
research-only and not redistributable, so they are for comparison with published work, never for product claims,
and only through download adapters.

## 9. Code

Python, MPL-2.0. **Decided (2026-11-22):** the harness is written in Python. UberScene's read-only commands are
called through its CLI; edits go through `uberlens-bridge`, a small Node JSON interface over the SDK, because the
CLI has no mutation commands (section 6). Python suits the media tooling and the benchmark.

```
uberlens/
  state/        # versions, evidence store (SQLite + blobs), working files, coverage, budget, log
  media/        # probe (ffprobe / PyAV), frames, audio, transcribe
  prior/        # activity profile, partition, first-look placement
  explore/      # catalog, overview, inspect, listen, transcribe, retrieve
  edit/         # client for the bridge: actions, apply, undo; check, look, excerpt; critic
  decide.py     # the decision interface and its log
  server/       # MCP server, CLI, skill
bench/
  tasks/        # manifests: sources (with hashes), briefs, labels, checks
  inject/       # defect injection for Repair
  score/        # per-family scorers, judge, cost report
  run.py        # runs an agent with or without the harness
bridge/         # uberlens-bridge: Node, UberScene SDK, JSON over stdio
tests/
```

## 10. Milestones

0. **M0, prove the integration.**
   - The bridge: a trim is dry-run, committed to `video.tsx`, reloaded in a fresh process, and undone, with the
     expected-revision check refusing a stale edit.
   - Render the same file twice and compare frame hashes; record what the frame-cache key covers.
   - License check of candidate footage and of AgenticVBench. Pick the first models.
1. **M1, one evidence-backed edit on real footage.** The Find → Repair task end to end: catalog, overview,
   inspect with burst, listen, transcribe; observations and claims with kind-based sufficiency; the bridge;
   `check`, `look`, `excerpt`, the critic. **Acceptance:** a real model, on held-out footage, locates an
   independently labelled phrase, cites the observations it used, applies a typed trim, and the rendered output
   passes the independent verifier, including the cases where the phrase is absent. A scripted fake model is
   used only for unit tests, with events whose location changes between runs, so a fixture cannot pass by knowing
   the answer.
2. **M2, the three comparisons** of section 8.3 on a few dozen Find → Repair tasks, at matched budgets, with
   paired intervals. This is the first UberLens result.
3. **M3, benchmark v0.** Answer, Assemble, Repurpose; the runner and cost report.
4. **M4, experiments.** The activity prior's paired re-encode test (activity-prior.md section 9), the belief
   scheduler, the remaining ablations, AgenticVBench for comparison, and whether a fast scorer is worth building.

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
