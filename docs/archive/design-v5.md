# UberLens: design

UberLens is two things:

1. **A harness** that lets a general agent (Claude Code, Codex, any tool-calling model) **explore** video and
   **edit** it. It gives the agent ways to look only where it matters, remembers what was seen and in which version
   of which file, makes edits through [UberScene](https://github.com/prefix-tree/uberscene), and checks the rendered
   result before calling it done.
2. **A benchmark** that measures how well an agent explores and edits, with and without the harness, on footage
   that can be redistributed.

UberLens trains no model. It is tools, state, prompts and checks around a model you choose.

Status: design, fifth version. External reviews are folded in. The latest, an adversarial one, separates the
product from the research, narrows the first experiment to interview selects with three competing agents, and
makes most of the machinery below earn its place before it is built (sections 1.1 and 10). It replaces the first draft, which described a question-answering agent with
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
- **Agents fail by drowning** (May 2026 data, older models). On AgenticVBench, 83% of failed repurposing tasks spent the budget transcribing or
  thumbnailing the whole source and never assembled an edit; 65% of failed repairs looked in the wrong time window.
  The harness's job is to make the cheap, targeted look the easy path.
- **Exploration serves an editorial decision.** The same moment needs different attention at each stage of an
  edit: is this take worth keeping (logging), does this passage earn its place (rough cut), where should the cut
  land (fine cut). The open decision says what to look at next, so the pass is part of the state (section 4), and
  the first milestones are the passes where exploring decides what the editor has to work with: selects, stringout,
  rough cut.
- **UberScene removes the hard half.** The editing papers build their machinery on FFmpeg commands. In UberScene the
  edit is one TSX file changed through typed, validated, undoable actions, with lint, layout checks, labelled
  contact sheets and a per-frame render cache. UberLens uses these instead of rebuilding them.
- **The core claim is traceable edits.** UberLens keeps the link between a moment in the source, the editorial
  decision that uses it, and the rendered output, across repeated revisions. That makes an edit traceable; it does
  not make it correct or good (section 4 separates the three).
- **Existing benchmarks leave a gap, a narrow one.** Two come close. AgenticVBench (100 post-production tasks,
  May 2026) and Timeline-Bench (arXiv:2609.35143, September 2026: 56 complete jobs from raw footage and a brief to
  a finished video) both make an agent find material in long sources and cut it, across several models and
  harnesses; Timeline-Bench also reports cost per run. Neither scores the looking: only the delivered video is
  graded, so a missed moment and a bad cut are the same failure, and no answer has to cite its evidence. Neither
  compares a video harness with the bare model at a matched budget. Neither can be handed on: Timeline-Bench's code
  is Apache-2.0 but its footage is gated and not redistributable. The sets that do redistribute openly licensed
  video (AgentVidBench, MMTB) test question answering or file handling, not editing. What is missing is one
  redistributable set that scores finding and editing separately, with cited evidence and code-checked repairs,
  for the same model with and without a harness.
- **The bottleneck may be craft, not compliance.** On Timeline-Bench, 16 agent setups resolved 14.0% of 896 runs,
  and 562 of the 771 failures passed every delivery, content and brief test and failed only on quality. Agents cut
  0.72 times as often as the reference edit, saw footage as stills and transcripts, rendered 72–90% of the way
  through a run, aimed 5.5% of their fixes at pacing, story or shot choice (against 66% of editors' notes), and
  claimed success in 93% of runs. No harness or guidance contrast there was significant. So checks and evidence
  tracking alone will not make a good editor; that is why product and research are separated below, and why the
  first build is a job where the editor keeps the craft decisions.

### 1.1 Product and research are separate

**The product** is an agent workspace that preserves source evidence, editing decisions and revisions. It does
not need a new exploration method to be useful.

**The research** asks whether evidence-aware exploration improves editorial outcomes. A more structured,
observable process makes an agent easier to debug, audit and reproduce. That is not the same as making it a
better editor: agents can pass every mechanical check and still fail on editorial quality. The design holds four
separate hypotheses, and each has to be shown on its own:

| | Hypothesis | Tested by |
| --- | --- | --- |
| H1 | Explicit observation provenance, coverage and claim rules find what is in the footage more reliably than generic media tools | Agent C vs B (section 10) |
| H2 | Knowing the editorial decision at hand improves what the agent chooses to look at | A source index built without the brief vs exploration conditioned on the brief, same editing policy |
| H3 | Recorded approvals and decision dependencies reduce unwanted changes and improve cuts | Pass-aware vs single-loop editor (section 8.3) |
| H4 | A critic that watches and hears the render beats one that reads the timeline | Section 8.3 ablation |

Exploring and editing are different problems. Exploring reduces uncertainty about what the footage holds;
editing makes something good under creative constraints, and finding every relevant passage can produce a worse
cut than finding three strong ones. So nothing here is assumed to help editing until an experiment shows it.

**The baseline everything must beat** is simple: a full timestamped transcript, a shot index and searchable media
references, handed to a general coding agent. No concrete failure of that baseline on interview selects has been
shown yet. Until one is, the observation taxonomy, claim checks and adaptive search are unproven, and the first
experiment (section 10) exists to find out.

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

**Versions.** Content and location are separate. `content_id` is the hash of a file's bytes; an **asset** is a
logical source that records which `content_id` sits at which path over time. Moving an unchanged file keeps its
content identity and its evidence; rewriting it makes a new content version, and nothing is ever silently
reattached to a newer one. (VIVID hashes path and content together, so a move makes a new identity.) Verified
identities are cached by size and modification time and re-hashed when either changes.

A **project revision** is the hash of `video.tsx` plus the manifest; every edit names the revision it expects
(section 6.1). That boundary is stated, not total: imported code, UberScene and Chrome versions and outside
configuration are recorded beside the revision, and a change in any of them is reported with a render. A **render** is
identified by the hash of the output file it produced. Approval attaches to that file, not to inputs predicted to
produce it.

Hashing full files costs time on long sources. It is charged to cold start and reported separately from the cost
of later questions on the same file.

**Observations and claims** (VIVID, OmniAgent; the split is **ours**). The store keeps two kinds of row, because
a versioned frame proves what the system *showed* the model, while a caption is the model's *interpretation* of it.

```python
class Observation(BaseModel):          # written by the harness only; immutable
    obs_id: str                        # "ob_" + 24 hex
    version: str                       # content_id of the source, or the render's file hash
    instrument: Literal["overview", "frames", "burst", "audio", "transcript", "check"]
    requested: Span                    # the media range asked for
    pts: list[float]                   # presentation timestamps actually decoded
    max_gap: float                     # largest gap between consecutive samples, seconds
    crop: tuple[int, int, int, int] | None
    payload_id: str                    # hash of the exact image sheet or audio handed to the model
    payload: dict                      # its form: sheet size, cell size in pixels, order, compression;
                                       # or audio sample rate, channels, duration
    model_call: str | None             # the call that consumed it
    anchors: list[str] = []            # media terms that survive trims: "word:12", "shot:3"  (ours)
    created: datetime

class Note(BaseModel):                 # written by the model about an observation; kept apart from it
    obs_id: str
    text: str                          # an interpretation, never ground truth
    model: str
    created: datetime

class Claim(BaseModel):                # descriptive: what happens in the footage
    claim_id: str
    kind: Literal["read_text", "presence", "order", "spoken_words", "audibility", "location", "absence"]
    text: str
    span: Span
    cites: list[str]                   # obs_ids
    expected: str | None               # stated before the look, when the agent states one
    verdict: Literal["confirmed", "partial", "not_found"] | None   # required when `expected` is set
    eligibility: Literal["eligible", "ineligible"]                 # set by the store, from the table below
    verified: Literal["unverified", "verified", "refuted"] = "unverified"   # set only by an independent check
    provenance: Literal["observed", "index"]

class Judgment(BaseModel):             # editorial: why a passage may work for this brief
    judgment_id: str
    subject: str                       # a select, a segment, an ordering
    text: str                          # "a strong opening: the admission lands before the explanation"
    rests_on: list[str]                # claim_ids: the facts it depends on
    alternatives: list[str] = []       # what it was weighed against
    author: Literal["agent", "editor"]
```

**Three things the store keeps apart** (the distinction is from review; the wording is **ours**):

| | What it establishes | Who can establish it |
| --- | --- | --- |
| **Provenance** | Which input the harness handed to the model, in which form | The store, exactly |
| **Coverage** | Whether that input could plausibly have shown the thing | The store, by the rules below |
| **Correctness** | Whether the evidence really supports the claim | Only an independent check: a human, a second model family, or a benchmark label |

A valid citation is not proof. The model can be shown a blue cup and claim a red one with a perfect citation. So
the store never calls a claim "supported": it marks it **eligible** (its citations could show such a thing) or
not, and `verified` stays unset until something independent checks it. The record covers what the harness
submitted; a hosted model may resize or recompress the input again, out of sight.

**Eligibility depends on the claim's kind**, not on a count of looks:

| Claim | Eligible when the cited observations include |
| --- | --- |
| `read_text` (a sign, a caption, a label) | A crop whose payload shows the text at a legible size |
| `presence` (X is in this shot) | A frame of that shot at a size where X can be made out |
| `order` (A happens before B, who handed what) | Samples covering both, with a sampling interval shorter than the event |
| `spoken_words` (where a phrase is said) | Word-timed transcript of the span, with its alignment confidence |
| `audibility` (is the line clear under the music) | The actual audio of the span, not only a transcript |
| `location` (when X happens) | An observation inside the span at an interval that could show X |
| `absence` (X does not happen) | Never eligible from samples; reported as "not seen at this coverage" |

**Editorial judgments are not claims.** "This is a strong opening" cannot be settled by evidence rules, and the
store does not pretend otherwise. A judgment names the facts it rests on (which are claims) and what it was
weighed against; it is settled by alternatives, taste and the editor. A select's reason is a judgment.

Pixels and audio leave the context after each step; a one-line stub with the observation id and timestamps stays
(OmniAgent). Rows go in SQLite, payloads by content hash. A transcript keeps the recogniser's confidence per
word, and recognised words are not treated as verified words.

**Working files** (VIVID): `TASK.md` (the brief), `PLAN.md` (the current plan, size-capped), and a generated index
of the evidence. An agent that runs out of context writes a checkpoint and continues in a fresh one; the budget
carries over.

**Editorial pass** (**ours**; the passes are standard editing practice). The pass belongs to a **decision**, not
to the whole project: a real project can have a locked opening, a rough middle, a fine-cut ending and unreviewed
takes at once. Each part of the cut carries its own pass, its approvals and what it depends on; a project-level
pass exists only as the default working mode. The pass sets what the agent is deciding there, which instruments
and evidence fit, and what "done" means. A review note can reopen a decision and whatever depends on it ("the
change feels unmotivated" reopens the search of the source for that segment), and that is recorded.

| Pass | What the agent decides | Evidence that fits | Hands forward |
| --- | --- | --- | --- |
| **Ingest and log** | What footage exists; sync and media problems; which takes or passages are worth keeping | Probing and checks by code; transcript search; listening to competing takes; overview and inspect for visuals | A source inventory and a **selects list**: source ranges, why each might be useful, and what is still unreviewed |
| **Stringout** | An order the editor can watch, with meaningful alternatives kept visible | The selects and their context | A playable assembly linked to the source, alternates included |
| **Rough cut** | What each passage does for the story, what can go, which order lands. For dialogue, a radio edit first (sound only decides the structure) | Words and delivery; going back to the source for what is missing | A playable rough cut, each segment with its purpose, open decisions listed |
| **Fine cut** | Local timing, delivery, angle changes, reaction beats, audio overlaps, inside the approved structure | Bursts and audiovisual excerpts around known cuts | Precise changes the editor can play and compare |
| **Lock and finish** | Records the approved picture revision; sound, colour, graphics and checks run against it | Code checks on the render | A traceable approval and verified deliverables |

Two rules:

- **Stringout and rough cut stay separate.** A stringout answers "what material do we have?"; a rough cut answers
  "what are we saying?". If they collapse, the agent's first search results become the story before the editor
  has seen the alternatives.
- **Approvals are state.** A select, a segment's purpose or a structure the editor approved is recorded with the
  project revision it was approved at. Later work must not disturb approved material without saying so; a
  structural change after lock explicitly reopens the cut and marks the affected work for review.

```python
class Select(BaseModel):
    select_id: str
    source: str                    # asset (a logical source)
    span: Span
    anchors: list[str]             # "word:412".."word:455", so it survives re-timing
    reason: str                    # why it might be useful for this brief
    cites: list[str]               # observation ids
    alternates: list[str] = []     # other takes of the same thing
    status: Literal["proposed", "approved", "rejected"]

class Decision(BaseModel):         # anything the editor approved or left open
    decision_id: str
    pass_: Literal["log", "stringout", "rough", "fine", "lock"]
    subject: str                   # a select, a segment, the order, the picture revision
    state: Literal["open", "approved", "reopened"]
    depends_on: list[str] = []     # other decisions; reopening one flags these
    revision: str                  # project revision it applies to
    note: str | None               # the editor's words
```

UberLens owns the source references, decisions and approvals, so a project can continue with a different model.

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

Cheap layers computed when a file is first cataloged, cached by `content_id`, reused by every later question or
edit:

- **Activity profile** ([activity-prior.md](activity-prior.md), **ours**): bitrate, keyframes and audio energy per
  second, with reliability checks. Measured cost: 0.07 s per minute of video for the container signals.
- **Shots and silences**: from UberScene's manifest when the footage is in an UberScene project; otherwise cuts from
  the activity profile.
- **The uniform half of the first look**: the evenly spaced overview frames, which do not depend on the question.

**Transcripts.** For dialogue-led footage (an interview, a talk), the word-timed transcript is part of ingest: it
is built once by code, cached, charged to cold start, and it is how logging finds passages. What stays ruled out
is the failure seen on AgenticVBench: spending a task's budget transcribing or thumbnailing everything inside the
agent's loop and never assembling the edit. For footage that is not dialogue-led, transcription stays on demand,
by span. A transcript finds where something is said; whether a take is usable is judged by listening
(`audibility`, delivery), not from the words.

### 5.3 Layer A: instruments

| Tool | Does | Limits | Source |
| --- | --- | --- | --- |
| `catalog` | Lists sources with duration, streams, versions, what is cached | | VIVID |
| `overview(source, profile)` | First look, **per question**: ForeSeek's N(T) = clip(round(10 + 3·log2(1 + T/600)), 10, 20) frames as contact sheets of 8 with timestamps. Half are the cached uniform frames; half are placed by the activity profile under `profile` | `profile` is required | ForeSeek, **ours** |
| `inspect(source, span, n, roi)` | Frames spread over a span, optional crop | ≤ 24 frames, span ≤ 600 s; a larger request returns a bounded window and the next request | VIVID, OmniAgent |
| `inspect(..., interval=…)` (a burst) | Consecutive samples at a stated interval, for order, motion and "who handed what" | ≤ 24 frames; the agent sets the interval, so the span is at most 24 × interval (0.8 s at 30 fps, 8 s at 3 fps) | OmniAgent `get_clip`, ActiveForager's temporal zoom |
| `listen(source, span)` | Loudness, waveform and spectrogram summary, speech presence | ≤ 120 s | VIVID |
| `transcribe(source, span)` | Local Whisper for a span, word timings; partial results kept | spans, never the whole source by default | VIVID |
| `retrieve(query \| id)` | Exact lookup by id, text search over observations and claims, filters by source, time, kind; claims come back marked eligible or not, and verified or not | | VIVID |

**`profile` runs before every overview.** The agent picks how the activity half is placed for this question:
`motion` (events and actions), `speech`, `cuts` (scene or topic changes), or `off` (static details such as a sign
or a face: all frames uniform). Models lock onto the most visually striking scene (NEST), and an activity-guided
skim makes that worse for a static-detail question, so there is no default: the choice is made and logged each
time. The uniform half is always kept.

**Why burst exists.** `inspect` at its widest is 24 frames over 600 s, one frame per 25 s. That finds a scene; it
cannot show an event inside it. A burst trades span for density on purpose, within a fixed frame budget. Naming a
look a burst does not make it fit for motion: a 150 ms handoff is missed at 3 frames per second, and a slow
20-second move needs only sparse samples. So every look returns its actual sampling interval, and eligibility for
`order` compares that interval with the event's length. A short interval still does not prove the event was
caught.

Every instrument returns the presentation timestamps actually decoded, the largest gap between them, the version,
the crop and an observation id. A requested span and frame count can overstate what the model had a chance to
see; the decoded timestamps cannot.

### 5.4 Layer B: honesty

- **Every look is an observation** written by the harness (section 4): version, decoded timestamps, largest gap,
  crop. The model's note on it is an interpretation.
- **Every descriptive claim cites observations**, and the store marks it eligible or not for its kind (section
  4). A claim without citations is a guess and is reported as one. Eligible is not correct: correctness comes only
  from an independent check, and the benchmark scores against labels, never against citation shape alone.
- **Editorial judgments are kept apart** from descriptive claims and are not put through evidence rules.
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
5. Stop by the kind of question (below). Otherwise report what is known and where the gap is.

| Question | When to stop |
| --- | --- |
| Existence ("is there a shot of the factory?") | After one eligible positive |
| Exhaustive ("every time she mentions the price") | One positive proves nothing about the rest: stop on coverage, and report what is unreviewed |
| Comparative ("the clearest take of the answer") | Not after the first candidate: look at the alternatives first |
| Editorial selection ("a strong opening") | A stated exploration budget and a coverage report; stopping at the first adequate candidate is satisficing, and the goal is the best of what is there |

Whether an evidence-based stop beats a plain fixed budget on creative tasks is untested; the first experiment
uses a fixed budget.

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

This loop runs inside a pass (section 4), and the pass decides what `review` looks for. In the stringout it only
checks that the material plays and links to its source. In the rough cut it reviews structure: does each segment
do the job its purpose states, heard as a radio edit first. The watching critic of 6.3, with excerpts around cuts,
belongs to the fine cut.

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

- **Diagnosis and remedy are separate.** The critic first says what is wrong. A remedy is optional: when it gives
  one, `fix` must be in `actions(element)` and pass a dry run, or it is rejected before the editor sees it
  (**ours**; it removes EditDuet's failure of invented functions). The critic may also answer "no acceptable local
  fix", which reopens the decision above (the segment's purpose, the order) instead of forcing an atomic edit onto
  a structural problem.
- **Scores are a weak signal.** A 1–5 rating of a segment in isolation is noisy, and a segment that passed can
  fail once its neighbours change. For craft, the critic also compares two rendered alternatives side by side;
  whether pairwise judgments beat absolute scores is part of H4.
- **The critic shares blind spots with the editor** when both are the same model. Real audio and video reduce
  that; they do not remove it.
- `plan` failures go back to planning; the rest go to the editor (Auto-Director's routing).
- Approval is tied to the render file it was given. A frame-cache hit does **not** carry approval forward: an
  unchanged frame can sit beside a different cut, against different narration or under a different mix, and
  UberScene's cache keys media by size and modification time and does not see `--import` code. Frame keys are used
  to reuse images, not verdicts.
- A segment that passed is reviewed again when an edit touches it, when a neighbour changes, or when a decision it
  depends on is reopened. After any timing change, the transitions on both sides of the edit are reviewed again.
- The number of rounds is a budget setting, 3 to start (Auto-Director's value, not validated for this workflow);
  the effect of the limit is measured. At the limit the agent returns the best version, with failing segments and
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
  time, next to accuracy. Preprocessing is reported both ways: the total cost of a one-off task, and the cost
  spread over repeated tasks on the same source, so a system that front-loads work cannot look cheap by hiding it.
- **Outcomes over behaviour.** Counts of observations, valid citations and preserved approvals show how an agent
  worked; they also happen to be things UberLens is built to produce, so a benchmark that rewards them would
  measure whether an agent follows this architecture. The primary measures are outcomes: the quality of the final
  render and the effort a human editor needs to finish from it. Behavioural measures are reported beside them and
  never decide a comparison.
- **One primary outcome and one hypothesis per experiment.** Many models times many policies times many families
  at 20 tasks each gives a matrix of inconclusive results. Each experiment names its outcome and its hypothesis
  first, uses paired tasks grouped by source, and grows only after a signal.

### 8.2 Tasks

| Family | Task | Scored by |
| --- | --- | --- |
| **Select** (logging) | An interview and a brief; return a ranked shortlist of passages worth keeping | **Outcome:** blind editors rate usefulness, ranking, missing alternatives and wasted passages, and how long it takes them to reach an acceptable assembly from the shortlist. Beside it: recall of labelled passages, whether the source ranges are right and playable, whether each stated reason matches the source |
| **Revise** (rough cut) | A rough cut with approved segments and one review note that forces a return to the source ("find a stronger reason for the pivot, but keep the opening") | By code: how much approved material was disturbed; is the substitution grounded in the footage. By editors: is the revision acceptable. Also time and cost to an acceptable revision |
| **Find** | "Where does X happen?" in sources from 5 minutes to 2 hours | Overlap of the answered span with the labelled span; whether the cited looks fall inside it at a density that could show the event |
| **Answer** | Questions needing one or several moments, including static details, speech, order and motion | Correctness; **support**: do the cited looks cover the labelled spans; a right answer with wrong or missing support is counted separately; split by question type (event, speech, static detail, order or motion, far-apart moments) |
| **Find → Repair** | A long source and a draft whose cut misses a specific spoken phrase (or another injected defect: a caption off its word, a clipped title, a wrong clip, bad levels). Find the moment, cite the source span, apply a typed fix, render. Includes cases where the phrase is absent and distractors that sound alike, so a confident guess can fail | **Grounded repair success**: an independent verifier finds the phrase and the cut in the rendered output, the cited source span is right, and unrelated edits are preserved. Also: localization error, false completion, wall time, cost |
| **Assemble** | A storyboard and a pool of clips with distractors; build the cut | Right clip per slot, order, durations, all by code |
| **Repurpose** | A brief ("60-second vertical teaser from this talk") | Code checks for format; yes/no rubric items for content, judged as in 8.4 |

The families follow the passes: Select and Find for logging, Assemble for the stringout, Repurpose and Revise for
the rough cut, Find → Repair for the fine cut.

About 20 tasks per family is enough to debug the benchmark, not to decide small differences: one task moves a
20-task score by five points. Claims about a few points need more tasks, and results are reported with paired
uncertainty intervals grouped by source video.

### 8.3 What gets compared

Every comparison is at matched budgets.

| Comparison | What it answers |
| --- | --- |
| Native agent vs full UberLens (VIVID's protocol) | Does the whole product improve task completion? |
| Same model and the same UberScene actions, with generic media tools vs UberLens's observation and claim tools | What UberLens's own design adds when both arms can make the same edits |
| Same model, footage, tools and budget: a single-loop editor vs the pass-aware one | Do explicit passes, pass-specific criteria and recorded approvals improve rough cuts and reduce rework? |
| Same harness, uniform vs activity-guided first look | Does the activity prior help search at the same first-look budget? |

The second and third rows are the ones that matter for the design. The second shows what the observation and
claim tools add; the third is the research question of the first build. For the third, editors review the renders
blind for story coherence and fidelity to the brief; then both systems get the same revision note, and rework is
measured as in the Revise task. Both arms get the same human input (the same brief, the same notes, the same
approvals), otherwise passes are confounded with extra guidance. It is repeated with a second model to see whether
the result holds across models.

- Further ablations: uniform first look instead of `overview`'s activity half, no burst, no required verdict, no
  claim-kind sufficiency, the belief scheduler on, no evidence store, no `check`, no `review`, and a critic that
  reads the timeline instead of watching the render. No paper has run the last one.
- Reference points: uniform frames into one model call; a transcript-only agent.

### 8.4 Judging

Anything code can decide, code decides. A model judge is trusted per agent, not per edit: Timeline-Bench's
three-judge panel tracked editors' preferences across agents (ρ = 0.93) but barely agreed with them on single
edits (κ = 0.15). Its top agents could not be told apart at one run per task (about ±11 points), so small task
families need repeated runs. Rubric items use a model judge from a **different family** than the agent
and critic, validated against human grades on a held-out set before its numbers are reported; the agreement is
published with the results.

### 8.5 Questions the first run should answer

1. How many points does the harness add to the same model, on each family, and at what extra cost?
2. Does an activity-guided first look beat a uniform one at the same frame count, on the same footage re-encoded
   several ways? (activity-prior.md section 9.)
3. Does ForeSeek's belief scheduler help an untrained model over the default narrow-and-change-one-thing
   search, or is it overhead?
4. How often does the critic approve a bad edit, and does watching beat reading?
5. Does a pass-aware editor produce better rough cuts and less rework than a single-loop editor with the same
   model, tools and budget?

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

The first experiment is deliberately narrow: **one task, three agents, no cut**. Given a 45 to 90 minute interview
and a brief, find and rank the best passages as source-linked selects an editor can review. No stringout, no
rough cut, no critic, no approval states: those add variables before the exploration method has shown any value.

| Agent | Has |
| --- | --- |
| **A. Baseline** | The full timestamped transcript, a shot index, ordinary media inspection, structured selects as output |
| **B. Exploration** | A plus the adaptive overview, crops and bursts |
| **C. Evidence** | B plus observation provenance, coverage and the claim rules |

All three get the same brief, source and budget, preprocessing included. Editors, blind to the agent, judge the
selects for usefulness, ranking, missing alternatives, wasted passages, and whether each stated reason matches the
source. **Primary outcome:** the time an editor needs to turn a shortlist into an acceptable assembly.

What the result decides:

- **B no better than A:** the exploration instruments are not needed for dialogue footage; build the product on
  the transcript-first baseline.
- **C no better than B:** the evidence machinery is overhead for this task; keep the provenance log for audit and
  drop the claim rules from the agent's loop.
- **Neither reduces the editor's effort:** the benefit does not matter to the product, whatever the select scores.

0. **M0, prove the integration.**
   - The bridge: a trim is dry-run, committed to `video.tsx`, reloaded in a fresh process, and undone, with the
     expected-revision check refusing a stale edit.
   - Render the same file twice and compare frame hashes; record what the frame-cache key covers.
   - License check of candidate footage, dataset by dataset and asset by asset. Pick the first models and write
     down what each must support (tool calls, images, audio, context size); certify those few before claiming
     any model works.
1. **M1, source log and selects.** Ingest (content identities, media checks, the transcript with word
   confidence, shots), the three agents above, the selects format with a jump to the source, and the decision
   log: which interval, instrument and density each agent chose. That log is kept whatever the result; it is how
   a good search policy can be found from data and not written in advance.
2. **M2, the three-agent experiment** with editors. Then decide, from the three outcomes above, how much of
   sections 4 and 5 gets built.
3. **M3, stringout and radio rough cut**, with decisions, approvals and one revision note that forces a return
   to the source. Only after M2 shows a signal.
4. **M4, the pass-aware comparison** (H3) and the Revise measures, with a second model.
5. **M5, fine cut** (H4): the watching critic, pairwise judgments, Find → Repair.
6. **M6, benchmark v0 and the remaining experiments:** H2, the activity prior's paired re-encode test, the belief
   scheduler, external benchmarks.

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

1. Which models first, for the agent, the critic and the judge (the judge must be a different family)? Models
   differ a lot in tool calling, media support, caching, context and cost, so "any tool-calling model" is a goal,
   not a starting claim.
2. Which footage for the benchmark, and who labels it?
3. Who are the editors for the blind review, how many, and how is their agreement measured? Without them the
   pass-aware comparison has only the code-scored rework measures.
4. Has a pass-aware editing agent already been published? Not checked; the editing research
   (research-editing.md) found planner, critic and index-first systems, none organised by editorial pass.
5. Does UberLens also need to edit footage that is not in an UberScene project? If yes, the first step is
   wrapping it in one.
6. The benchmark's name, and whether it lives in this repo or its own.
