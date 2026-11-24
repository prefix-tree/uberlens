# UberSeek: design

UberSeek is a harness for video work: one reusable environment that brings together what an agent needs to work
with video. It does not have an agent loop of its own. It runs inside an existing agent harness, Pydantic AI,
which drives the model and calls UberSeek; that is also how it is tested end to end.

It has two layers:

- **A base for exploring video.** A programmable environment: the agent writes small programs against a typed
  video API to search, measure and filter footage, and asks to be shown images of the footage only where a judgment
  needs it. Sources, observations, cost and task completion live here. It knows nothing about editing. Anything
  that needs to look at video can be built on it: question answering, search, review, selection.
- **Modules on top.** The first is **selection**: finding the moment that is needed, choosing the best candidate,
  and setting where it starts and ends.

It is built in iterations. The first iteration is the base plus the selection module. Later iterations add
carrying out edits, reviewing the result and handling revisions (section 9).

**Status.** M0 is built, and M1 is under way (cuts, the transcript, real footage, and a check that two models
read the pictures correctly). M0 gave: exact frames and sound from FFmpeg, the observation log, `observe` as a tool in
Pydantic AI, and the proof that an observation can be made again exactly (section 7). The typed API and the
executor come next, in M1.

This is the one maintained document. Everything earlier (the research reports, the activity-prior notes, previous
designs) is frozen in [archive/](https://github.com/prefix-tree/uberseek/tree/main/docs/archive) and is cited here by file name where a number comes from it.

## 1. Why moments come first

- **Agents produce conforming files; they do not yet edit well.** On Timeline-Bench, 857 of 863 delivered videos
  passed the delivery-format tests (codec, size, frame rate, sound, duration), but only 14.0% of runs were
  resolved. Format checks do not show that the right sources were used or the shots were well chosen
  (`research-validation.md`).
- **Selection is a plausible bottleneck, not a proven one.** Agents there cut 0.72 times as often as editors, and
  only 5.5% of their own fixes concern pacing, story or shot choice, against 66% of editors' notes. The same
  benchmark also finds problems with structure, transitions, graphics and finishing. On AgenticVBench, 65% of
  failed repairs looked in the wrong time window.
- **Agents see stills and transcripts.** Those cannot show delivery, rhythm, or the instant an action lands.

Picking has three levels:

| Level | Question | Research so far |
| --- | --- | --- |
| **Locate** | Where in the footage is what I need? | Heavily studied (SAVE, ForeSeek, T\*, VideoTree) |
| **Choose** | Of several candidates, which is best for this purpose? | Benchmarked: picking one clip among candidates (VEBench), selected ranges by several professionals (MEDit-Bench) |
| **Trim** | Exactly where does it start and end? | Studied as cut-point prediction (Pardo et al., Huang et al., 2021) and as highlight and deletion spans (RoughCut-Bench) |

Choose and trim have public work and labels (section 8). What none of it tests is an agent that **decides what to
look at under a stated budget, compares several takes of the same content, sets in and out points
to sub-second error, and gives a reason for each boundary**. That is the gap this iteration aims at. Comparing
candidates is not new in itself (VEBench does it in one model pass, and the best model
picks the right clip 44% of the time and localises it at 0.11 overlap); the untested part is the agent controlling
its own looking.

### Editing is partly taste, not all of it

An editor's harder problem is often not seeing the footage but deciding what it means for the result wanted.
That judgment has three layers, and treating all of it as taste makes the problem harder than it is:

| Layer | Examples | How it can be judged |
| --- | --- | --- |
| **Technical** | Is a word clipped? Is the caption legible? Does it fit the duration? | Mostly by code |
| **Convention** | Does the cut feel abrupt? Is the speech clear? Does the reaction get enough time? | People largely agree on what is clearly bad; cut placement has been learned from edited film (section 8) |
| **Taste, intention, audience** | Dramatic or understated opening? Keep the pause? | Only relative to a brief, its context and whose preference it is |

So a moment has no quality score of its own. Its value is conditional: on the brief, on what surrounds it in the
cut, and on the preferences of the editor or audience. A two-second silence is a fact; whether it is dead air or
the strongest moment in the interview depends on what the piece is for.

## 2. The base: exploring video

### Three things that vary independently

| | What it is |
| --- | --- |
| **Extent** | How much time is under consideration |
| **Fidelity** | How finely it is shown: how many frames, at what size, with or without sound |
| **Objective** | What the agent is trying to find out |

The width of a span does not decide what should be shown. A 45-second passage may need only its sound ("is the
dialogue clear?"); a 3-second moment may need dense frames ("who takes the document?"); one frame can settle a
question about a 90-minute video. So the agent states an extent and an objective, and the harness chooses the
fidelity.

### The interface: code, plus a way to look

Video is far larger than what the next decision needs. So the agent does not call one inspection tool at a time
and read every result. It writes a short program against a typed video API; the program runs in a sandbox;
intermediate data (transcripts, timings, signals, a hundred candidates) stays there; only a compact result comes
back. This is Cloudflare's Code Mode idea applied to video.

**A shell for video.** A coding agent is effective because a few general operations (search, read, combine) let
it explore any codebase, with no special tool for each kind of analysis. The base follows the same principle:

| Operation | Like | Does |
| --- | --- | --- |
| `find(query)` | `grep` | Returns candidate spans that may match a description in words, or that resemble an earlier span |
| `observe(span, focus)` | `cat` | Delivers images of the footage to the model as an observation, by artifact id |
| `sheet(times, labels)` | A plot | Draws frames picked from anywhere in the video on one picture, in the caller's order |
| `execute(program)` | A shell script | Runs a bounded program that combines searches, measurements and looks, and returns its result |

- **The API is a small library, and `execute` is one way to run it.** A host that is itself a coding agent can
  import the library and write ordinary Python; a host without a shell calls `execute`, which runs the same
  program in the sandbox. There is no query language.
- **A skill teaches the surface; `guide` is `discover`, on request.** Tool descriptions say what each tool
  does, not how to work. The skill (`uberseek/skill/`, section 5) does: the method, the rules, and the detail in
  reference files. Its short core is always given; `guide(topic)` returns a reference file when the agent asks.
- **Memory is part of the runtime, not a tool to remember to call.** Every `find` and `observe` is logged as it
  happens, and a program can read the log (below).
- **The base does not know the creative task.** `ripgrep` does not know why a line is wanted. The base supplies
  operations that compose; the agent, and the modules above, supply the purpose.

```python
hits = find("interview.mp4", "company almost failed", limit=20)

candidates = []
for hit in hits:
    span = expand([hit["start"], hit["end"]], before=5, after=8)
    candidates.append({
        "span": span,
        "text": hit["text"],
        "pauses": pauses("interview.mp4", span[0], span[1]),
        "shots": len(shots("interview.mp4", span[0], span[1])),
    })

best = [c for c in candidates if c["shots"] == 1][:3]
for c in best:
    observe("interview.mp4", c["span"][0], c["span"][1], "delivery", "is the admission clear and unread?")
best
```

This runs as written (`uberseek/api`, `uberseek/exec`). The program is Python, run in a sandbox (section 5). Its
functions return plain values and times are seconds. The three pictures come back to the model beside the result;
the program itself never sees them.

**`find` returns candidates, never answers.** Search in video is not `grep`:

| | `grep` in code | `find` in video |
| --- | --- | --- |
| Match | Exact | A similarity score; "looks as if she lost trust in him" is not a predicate anything can test |
| No results means | It is not there | Nothing: the moment may exist and have been missed |
| Cost | Negligible | An index built once per source, then cheap |

So the rules for `find` are:

- **What it searches.** Today, the transcript: passages ranked by the words they share with the query. It
  matches words, not meaning. Later, if it earns its place, frames indexed by an image-and-text embedding model.
  Each candidate says how it was found and with what score. A score is an estimate (see signals).
- **Results feed the next search.** `after` and `before` restrict a search in time, so one result bounds the
  next. `like` will search for what resembles an earlier span, once pictures are indexed. "The same book appears
  again" is then two calls joined by a program:

  ```python
  opened = find("film.mp4", "opens the red book")
  later = find("film.mp4", like=opened[0], after=opened[0]["end"])   # needs the picture index: not built
  ```

- **It does not plan.** `find` is one retrieval, not an agent inside a tool. A composite question is composed by
  the agent in a program, where its cost and the reason for a failure stay visible.
- **A candidate is not seen.** It counts as found only after an `observe` of it.
- **An empty result needs a fallback.** The map and the ladder are how the agent looks where search found
  nothing, and `observations.coverage` says what has not been looked at.
- **It has to earn its place.** Picture search costs an index per source. If it does not locate better than the
  transcript plus the ladder, it is dropped and `find` stays text-only (E0).

**No answers from a hidden model.** `observe` could take a question and return a caption written by a second
model. It does not: that caption would come back looking like a fact, and the agent that decides would not have
seen the footage. `purpose` records what a look is for; the pictures go to the deciding model. Delegating a look
to a cheaper model is a possible later arm, logged as an estimate.

**Measurements are the exact part.** Word timings, pauses, loudness and cuts are deterministic and cheap, as
`grep` is. Programs use them freely (signals, below).

**Code computes; only the model perceives.** A program can search, measure, filter and rank on timings, words
and signals. It cannot judge framing, expression or whether a cut lands. Any decision of that kind needs an
`observe`, and only what `observe` delivered counts as something the model saw.

**`observe` delivers images only** (decided). Frames, contact sheets and crops, returned by artifact id. Images
are what every host and model can take in a tool result; sound and video clips are not. Sound reaches the model
in two indirect forms: as measurements (words with timings, pauses, loudness) and drawn as a picture (a waveform
or loudness strip with the words marked on it). The model does not hear anything in this iteration. So what
depends on hearing (hesitation, tone, clarity under music, the rhythm of a cut) is decided from signals, recorded
as **not heard**, and left for the editor to confirm. Real sound in `observe` is a later capability (section 9).

### Memory as part of the API

VIVID keeps every look outside the model's context, pinned to the file version it came from, and lets the agent
search it with one `retrieve` tool (`research-editing.md`). UberSeek keeps the same store, and makes it an object
in the API, so a program can query and reuse past observations like any other data:

```python
seen = observations("interview.mp4", focus="visual")

# Coverage: what has not been looked at yet, and what only from far away?
covered = coverage("interview.mp4")
never = covered["never"]
far = [look for look in covered["looked"] if look["gap"] > 2]
```

| Operation | Does | Built |
| --- | --- | --- |
| `observations(video, focus, start, end)` | Filters past looks by source, focus and time | Yes |
| `coverage(video, start, end)` | Says what was looked at, how closely, and what was not looked at at all | Yes |
| `show_again(id)` | Shows a past look again, from its stored picture | Yes, as a tool |
| Search over notes | Searches the model's notes on past looks | No: the model writes no notes yet. `purpose` is kept with each look |
| Pairing looks across versions | Pairs looks at the same moment in two versions of a file or render | No: needs a render to compare |

- **Notes are interpretations.** A search over notes is a search over the model's own captions, so a wrong caption
  comes back looking like a fact. Only the stored images are what was shown.
- **Re-showing is cheap to make, not free to see.** No decoding is needed, but the images go to the model again
  and count against the budget of views.
- **Usage is measured, not assumed.** In VIVID, agents called `retrieve` in only 10 to 32% of tasks, and its
  memory ablation removed the working files at the same time, so how much the searchable store itself helps is
  unknown.
- **Working files stay the host's job.** The brief, the plan and continuing in a fresh context belong to the host
  harness; UberSeek supplies a compact index of the observations and candidates for it to load.
- **Bounded requests.** A program or `observe` asking for more than its caps returns a bounded part and the next
  request to make, pinned to the same version (VIVID).

**The simple actions remain, as a library.** `zoom(span, focus)`, `back` and `done` are functions
built on the same API, and can be exposed as plain tools for a model that does better with a small vocabulary.
Whether code beats those tools is an experiment (E6), not an assumption: writing and debugging programs costs
output tokens, and Code Mode's published savings are for very large tool catalogues, not for a handful of video
tools.

`focus` says what a look is for:

| Focus | `observe` delivers |
| --- | --- |
| `visual` (default) | Frames, by the ladder below |
| `speech` | The words with timings as text, and the sound drawn as a waveform strip; few or no frames |
| `motion` | Dense consecutive frames over a short stretch |
| `delivery` | Frames of the speaker, with the sound drawn as a strip and its measured pauses and loudness |
| `boundary` | Consecutive frames around one instant, with the waveform and word boundaries marked |

### The ladder: the default for `visual`

| Level | Span | What is shown |
| --- | --- | --- |
| **Map** | The whole source | A frame per equal slice of time, the words under each, and one strip of measured loudness with silences and cuts |
| **Section** | Minutes | One frame per shot when the span holds eight shots or more, otherwise a frame per equal slice; the words under each |
| **Passage** | 10–60 s | A frame every second or two, with the words under each |
| **Moment** | 1–8 s | A dense run of frames, with the sound drawn as a strip |
| **Frame** | One instant | Full resolution, or a crop |

The ladder is a **default way to show a span**, a policy the harness applies. It is not the definition of
exploring, and it is not a fixed route: the agent can jump between sources, revisit, and look at spans that do not
nest.

### What the harness decides and enforces

- **The model owns the strategy; the harness owns the invariants.** Which candidate deserves another look is the
  model's call. Media validity, budgets, what fidelity was delivered and what is kept are the harness's. There is
  no required route through the ladder.
- **The harness sets fidelity; the agent sets extent and focus.** In SAVE, a harness rule for frame count and
  resolution beat the model's own choice by 3.7 to 5.8 points (`research-rres.md`). `focus` is a category, not a
  frame count, so that finding still holds here. This is a real tension with the principle above: Anthropic's
  guidance would give observation decisions to the model. The split is a starting position; letting the model set
  fidelity is an arm of E0.
- **Caps**, whatever the focus: frames per view, pixels, seconds of sound, and a budget of views, tokens and time
  per task. These hold inside programs too: the API enforces them on the host side, so a program cannot ask its
  way around them. The model never writes media commands.
- **Every observation states what it delivered:** the span asked for, the presentation timestamps actually
  decoded, the gap between samples, frame size, and which signals were drawn on it.
- **Seen is not heard.** A picture of a waveform is not listening. Anything decided about sound from signals and
  drawn strips is recorded as not heard, in the observation and on the selection it supports.
- **Observations leave the model's context** after each step; the log stays (section 4).

### Built once per source: signals

By code, cached by the file's content hash. A **signal** is a measurement over time, kept with where it came from:

| Family | Examples | Useful for | What it cannot tell |
| --- | --- | --- | --- |
| Speech | Word timings, pauses, repetitions, speech rate | Dialogue selects and trimming | Whether the delivery is good |
| Sound | Loudness, clipping, silence, onsets | Clear speech, emphasis, rhythm | Loud is not important |
| Motion | Cuts, camera and subject motion | Action timing | Still moments can be the strongest |
| Picture | Faces, framing, text legibility | Whether a shot is usable | Style |
| File | Bitrate, keyframes | Cheap hints of change | Mostly encoder behaviour |

Rules for signals:

- **Measured and estimated are kept apart.** A pause length is measured. "Speech clarity 0.88" from a model is an
  estimate, recorded with the model and version that produced it, and never treated as a physical quantity.
- **Signals guide where to look; they never decide.** The harness uses them to place the map, to offer boundary
  alternatives, and to point at what has not been heard or seen yet. A selection is never made because a number
  was high.
- **Each signal has to earn its place** against doing without it (section 6). The first build has the cheap
  measured ones: speech timing and pauses, loudness and silence, cuts.

For speech footage the transcript is part of this. On speech-heavy video it carries most of the locating (on
Video-MME long with a 7B model, subtitles score 65.4 and frames 52.0, `research-validation.md`), so `find` is the
first move there. Cold-start cost is reported separately from the cost of each task.

## 3. The selection module

The module turns exploring into an editorial decision: which moment, among the usable ones, for this purpose.

### The brief and the profile

A selection is always made for something. The module takes:

```python
class EditorialProfile(BaseModel):
    intent: str                  # what the cut should communicate
    audience: str | None
    style: dict[str, str] = {}   # pacing, emotional intensity, how much explanation, tolerance for silence
    constraints: list[str] = []  # duration, required content, source or brand rules
    examples: list[str] = []     # preferred and rejected choices, with reasons
    inferred: dict[str, str] = {}   # preferences guessed from behaviour, kept apart from stated ones
```

Stated preferences and inferred ones are separate. An editor accepting one dramatic cut does not mean they always
want drama. Engagement (watch time, retention) is an objective only when the brief asks for it; it is not the
definition of quality.

### Candidates are the working artifact

What persists between steps is not a summary of the video. It is the **candidate set**: the moments under
consideration for each purpose, what is known about each (signals, observations, the agent's assessment), and
what is still unknown.

### The default decision loop

1. Name the competing candidates for the purpose.
2. Ask what evidence could reverse their order ("the second one's delivery has not been heard").
3. Get the cheapest missing evidence, through the base.
4. Compare again.
5. Stop when more looking is unlikely to change the choice, or the budget is spent. Abstaining is allowed.

This is a habit the prompt and the candidate set make easy, not a numeric optimiser. Estimating the value of a
look in numbers needs a calibrated model of editorial utility, which nobody has; the archive's
`research-rres.md` covers why one-step value estimates are weak. Whether this loop beats plain range exploration
is experiment E4.

Two functions on top of the base, callable from a program or as tools.

### `compare`: choosing between candidates

`compare(candidates, purpose)` shows two or more candidates in a matched way, so they can be judged against each
other and not one at a time.

- Each candidate is shown as frames with its sound strip and words, and with a little of what comes before and
  after it.
- Candidates are matched on what they say or show, not forced to the same length.
- The order is randomised and each comparison is run in both orders, because model preferences between two items
  flip with presentation order in other studies (`research-validation.md`).
- The result names the preferred candidate for the purpose, and why, in terms an editor would use: delivery,
  clarity, usefulness to the story, composition, how it enters and exits.

Finding a relevant passage is retrieval. Choosing between two usable ones is a comparative judgment, and the
ladder does not solve it. This action is the main research target of the iteration (section 6).

### `mark`: selecting, with boundaries compared

`mark(span, purpose, why)` records a selection. Its in and out points are not just "seen up close"; they are
**chosen among alternatives**:

- For each boundary, the harness offers nearby alternatives (the end of a word, a breath, a pause; the start or
  end of a movement) and shows frames and the sound strip around each.
- The agent picks one and says why, or leaves the boundary **rough**.
- More than one cut point can be right, and the right one can depend on the neighbouring shot or the mix. A
  boundary is recorded as chosen for a stated reason, never as the single correct time.

### What comes out

```python
class Selection(BaseModel):
    source: str                  # content hash of the file
    start: Time                  # in point, in the source's own timebase
    end: Time                    # out point
    purpose: str                 # free text, optionally tied to a line of the brief
    signals: dict[str, Signal]   # measurements, each with its provenance
    assessment: Assessment       # the agent's judgment: strengths, weaknesses, why; separate from signals
    start_status: Literal["rough", "compared", "not_heard"]    # not_heard: sound-dependent, decided from signals
    end_status: Literal["rough", "compared", "not_heard"]
    observations: list[str]      # the observations it rests on

class Preference(BaseModel):     # one comparison, kept with its context
    preferred: str               # candidate id
    over: list[str]
    purpose: str
    profile: str                 # which brief and profile it was made under
    context: str | None          # what surrounds it in the cut, if known
    reason: str
    by: Literal["agent", "editor"]
    order_shown: list[str]
```

A preference is conditional: it holds for that purpose, profile and context, and does not make a universal
ranking. Preferences are stored as they were made. No preference model is trained from them until there are
enough independent, repeated judgments to test one; editorial preferences can be cyclic and differ between
people.

Selections export as JSON, a cut list (EDL), or an UberScene file. In the first iteration another tool carries
out the edit.

## 4. State

Everything lives outside the model's context, in the project folder, so a task survives a full context or a new
session and can continue with another model.

- **An append-only observation log**, readable from programs through `video.observations` (section 2). Each entry: the source and its content version; the span asked for and the
  timestamps decoded; the exact artifact shown (stored by content hash, with image size, sampling and sound); its
  cost and the model call that consumed it; and how it relates to earlier entries: `refines`, `compares`,
  `selected_from`. Agents jump between sources and revisit overlapping spans, so this is a graph, not a tree. A
  tree view is drawn from it when that is useful.
- **Candidates, selections and preferences**, as above.
- **Traces for improving the harness.** Which looks changed a decision and which were wasted is recorded, so
  changes to the harness can be judged on held-out footage and not on impressions. Held-out matters: the one
  published method that tunes a harness from its traces gains 7 points on the tasks it tuned on and 0.4 on others
  (section 8).
- **Executions.** Each program run: its text, the API calls it made, what it returned, whether it failed.
- **Cost**, per observation, per execution and per task.

**Time.** Positions are kept as presentation timestamps in the media's own timebase (a rational number), not as
floating-point seconds, so variable frame rate and audio alignment do not move a cut.

The log proves what the model was **shown**, not that it read it correctly. Correctness is only measured against
labels or checked by something independent (`research-validation.md`).

## 5. The harness

Kept thin until the method has shown a gain. The first build is the pieces below, hosted by an existing harness,
not a framework. A harness is an engineered environment in which the model can make and check useful decisions, not a
bigger orchestration layer:

| Mechanism | In UberSeek |
| --- | --- |
| Context kept small | Media and large outputs stay outside the model's context; only what the next decision needs is loaded |
| Durable state | Observations, candidates, selections and preferences persist across calls and sessions |
| A small surface | Three operations (`find`, `observe`, `execute`); the simple actions as a library on top |
| Checks before "done" | By code: selections play, source versions and timestamps are valid, constraints of the brief are met |
| Recovery | A long exploration resumes from the log |
| Delegation, only where isolation helps | Indexing and retrieval can run apart from the deciding model |
| Change by measurement | Harness changes are compared on held-out footage |

- **An environment, hosted by Pydantic AI** (decided in M0). The core is the typed video API, the bounded
  executor and the `observe` gateway. UberSeek has no loop of its own: Pydantic AI drives the model and calls it.
  The same tools can be offered to Claude Code, Codex or OpenCode. The host model keeps the exploration strategy.
  - *Why Pydantic AI.* A tool returns a picture as a typed value, and a scripted model can stand in for a real
    one in tests and receives the actual picture. It is a library, so UberSeek's tools are one small adapter
    (`uberseek/host/pydantic_ai.py`).
  - *Why not Hermes.* It can carry a picture in a tool result, through an internal convention, but it is a
    command-line application with a global tool registry, its own configuration and no stand-in model for tests.
- **Model contract.** A model needs tool calls and images, and the picture must arrive inside the tool result.
  Checked in M0 by capturing the request the host would send, with no model called:

  | Provider API | Where the picture goes |
  | --- | --- |
  | Anthropic Messages | Inside the tool result, after the text. Checked |
  | OpenAI Responses | Inside the tool output, after the text. Checked |
  | OpenAI Chat Completions | Not inside: in a user message after the tool result. Use Responses |
  | Google, Gemini 3 and later | Inside the function response, by the adapter's source. Not checked |

  What is not yet checked: that a real model reads the picture correctly. That needs an API key (section 10).
- **Media, behind one interface** of four calls: the file's facts, the index of every frame with its timestamp,
  the frames at given timestamps, and the sound samples for a span. Signals and pictures are computed above it,
  so a second backend only has to match those four. FFmpeg is the reference implementation and an inner tool of
  the harness, run by trusted host-side services. FilmCraft's codecs (through `uberscene-codec`) are an optional
  second implementation, to be used only after it matches FFmpeg on: the frame returned for a requested
  timestamp, variable-frame-rate seeking, sound and picture sync, colour conversion, behaviour around keyframes,
  and damaged files. What the model sees must be identical across backends in any experiment.
- **Exact frames.** A frame is chosen by its presentation timestamp, never by counting or by rounding seconds.
  Every decode reports the timestamps it produced, and they are checked against the ones asked for, so a wrong
  seek fails loudly and never returns a neighbouring frame.
- **Media services in Python**, Whisper for transcription.
- **One skill, written once, read two ways** (`uberseek/skill/`, a standard Agent Skill).
  - *What is in it.* A core of about 175 lines: the three operations, how to work (orient, narrow with code,
    look before deciding, zoom, check coverage, answer with what it rests on), six worked programs, and eight rules that each come from
    a mistake a model made with this tool. Five reference files: every operation, looking and reading a
    picture, writing programs, worked recipes, and what UberSeek cannot do.
  - *How it stays true.* The operations reference is generated from the library and the recipes reference from
    real programs. Tests run every recipe and every example through the executor, check each stated limit
    against the code, and fail when a generated file is stale.
  - *In the harness.* The core is the toolset's instructions, and `guide(topic)` returns a reference file.
    `toolset(..., skill=False)` leaves it out, so its effect can be measured.
  - *For a coding agent.* `uberseek skill install` copies it where the agent looks for skills, and the same
    operations are on the command line: `uberseek find`, `observe`, `run`, `guide`.
- **The model writes Python, run by Monty** (decided in M0). Monty is Pydantic's interpreter for a subset of
  Python, built for running model-written code: it runs in separate worker processes, has no files, network or
  environment unless the host passes them in, and takes limits on time and memory. Host functions can be async,
  and a run can be paused and resumed.
  - *Why Python and not TypeScript.* The services and the host are Python, so there is one language and no
    second runtime; and Pydantic AI already has a code mode on Monty to compare against.
  - *The cost.* It is a subset: no class inheritance, no generators, no `@property`, no `del`, no third-party
    imports. The API is therefore plain functions and simple values, and M1 measures how often models write
    outside the subset.
  - *What it is not.* Monty's isolation is an interpreter without those capabilities plus a process boundary. It
    is not an operating-system sandbox; a container around the worker stays an option if that is ever needed.

**Safe execution.** Programs written by a model run in a real isolation boundary (a separate restricted process,
container or isolate), never in the same process as the media services. A restricted `exec()` is not a sandbox.

| Boundary | Enforced by |
| --- | --- |
| Files | Read only registered sources and the project's own artifacts |
| Network | Off, unless switched on for a named service |
| Media processing | Only through the API; FFmpeg is called by host services, never by a generated shell command |
| Resources | Caps on decoded frames, pixels, seconds of sound, CPU time and parallel jobs |
| Output | Caps on returned text and media |
| Persistence | Selected results and metadata are kept; unbounded intermediate data is not |
| Reproducibility | Source identity, exact parameters, artifacts and outcome are recorded for every run |

```
uberseek/
  media/        # host-side media services; FFmpeg reference, uberscene-codec optional
  ingest/       # content hash, shots, sound, transcript, signals
  api/          # the typed video API the model programs against
  exec/         # the sandboxed executor and its limits
  observe/      # the observe gateway: focus, ladder defaults, caps, rendering, delivery
  state/        # observation log, executions, cost
  actions/      # zoom, back, find, done as a library and as plain tools
  select/       # the selection module: compare, mark, selections, export
  host/         # the adapter for Pydantic AI; model contracts
bench/          # tasks, scoring, cost report
```

## 6. Proof

**The research question.** Can an agent make better editorial decisions by selectively acquiring visual
evidence and comparing alternatives against an editorial objective, than by retrieving and ranking
candidates one by one?

The question is not whether the agent finds the most relevant moment. It is whether it can tell why one relevant
moment is editorially better than another, and what further look would help it decide. SAVE settles how to
locate; if this fails, the ladder may still be a useful interface, but there is no new method.

| | Experiment | Compared | Primary measure | Dropped when |
| --- | --- | --- | --- | --- |
| E0 | Does adaptive exploration help **locate**? | Full-video inference; a static index; SAVE, reproduced faithfully; UberSeek | Localization accuracy at equal total cost | It does not beat SAVE; then SAVE's loop is the base |
| E1 | Do **signals** improve selection? | Excerpts alone vs excerpts plus selected speech, motion and semantic signals | Blind editor preference; observation cost | Signals improve neither |
| E2 | Does **direct comparison** beat independent ranking? | Absolute scores; pairwise comparison with `compare`; ranking several at once; same candidates, context and budget, order randomised | Blind editor preference | Comparison is no better, or its verdicts flip with order |
| E3 | Does the **brief** change which moments are right? | General relevance ranking vs ranking conditioned on the brief, same footage under several briefs | Agreement with editors working to each brief | Conditioning adds nothing over relevance |
| E4 | Does **decision-led looking** beat the alternatives? | Free inspection (VIVID-style); SAVE; the ladder; the decision loop of section 3 | Editor preference, missed alternatives, cost, share of looks that changed a decision | It is no better than plain range exploration |
| E6 | Does **code** beat plain tools? | A: plain tools (`find`, `zoom`, `compare`, `mark`); B: the API through `execute` only; C: `execute` plus `observe` | Accuracy on locate, choose and trim; tokens in and out; round trips; wall time; failed or invalid programs | The model spends more writing and fixing programs than it saves; then plain tools are the surface |
| E7 | Are three operations **enough**? | The same surface on tasks of different kinds: short clips, long video, motion, sound, relations between events | Share of tasks solved with no new operation; which missing operation each failure would have needed | A kind of task fails for lack of an operation; then that operation is added and named |
| E8 | Can it do **compositional search**? | Find event A, use it to find a related event B (related in time, by structure, or by words); on both surfaces | A right and B right, scored apart; tokens, requests, time | Models cannot link B to A even with A found; then linking needs its own operation |
| E5 | Does **boundary comparison** improve trimming? | Transcript boundaries; silence boundaries; boundary comparison | Blind preference between boundaries; speech left intact | It does no better than the simple boundaries |

Rules for all of them:

- The same model in every arm, matched budgets with reasoning tokens counted, repeated runs.
- `compare` is ablated on its own, so a gain over SAVE can be traced to the ladder, to comparison, or to more
  reasoning.
- No arm hears. Every arm sees the same images and signals, so sound-dependent judgments are out of scope for
  these experiments and are reported as not heard.
- Full-video inference is always an arm: where evidence is not sparse it can make exploration unnecessary.
- Human cut points are not treated as the only right answer. On MEDit-Bench, professionals editing the same
  video for the same message agree at only 0.42 F1. So labels are **acceptable ranges from several annotators**,
  not one best candidate and one in/out pair, and agreement between humans is the ceiling a system is measured
  against.

**Data.** Locate has public sets with labelled moments. For choose and trim, two public sets are candidates,
licences permitting: VEBench's task of picking footage among four candidates and then localising it (with sound),
and RoughCut-Bench's highlight boundaries and transcript deletion spans (its media is redistributed; no raw
sound). MEDit-Bench was labelled with sound ignored on purpose, so it cannot test the sound level. No public set
was found with several takes of the same line or action and a preferred take, or with hand-marked acceptable cut
ranges on raw footage. That is the small set to label ourselves, with several annotators. Footage is interviews
plus action-heavy material.

**Size.** Small sets only show large effects: 20 tasks with 5 runs each detect about 17 points, 56 tasks with 5
runs about 10 (arithmetic under worst-case run noise, `research-validation.md`). The first run is a pilot that
measures the real variance.

**Other parts with a drop rule**

| Part | Dropped or simplified when |
| --- | --- |
| `focus` | Views chosen by focus do no better than the ladder's defaults |
| Looking, on speech footage | Transcript only matches it; looking becomes an escalation |
| File signals (bitrate, keyframes) | A plain map does as well |
| The profile's style fields | Free-text intent alone does as well |
| `video.observations` | Agents rarely query it, or tasks go as well without it; keep the log for audit and drop it from the API |

## 7. Milestones

One vertical experiment before a broad harness.

0. **M0, the observation contract. Built.**
   - *Media.* FFmpeg behind the four-call interface. Tests fetch every frame of seven clips one at a time, each
     with its own seek, and compare it with the same frame from playing the file through: B-frames, variable
     frame rate, HEVC, VP9, timestamps that do not start at zero, a cut that hides frames, and a rotated file.
     All match. Sound is cut where asked and placed correctly when it starts late.
   - *Observation.* `observe(video, start, end, focus)` picks the frames by the ladder, draws one picture
     (numbered frames, and the sound as a strip with measured pauses shaded) and states what it delivered.
   - *Log.* SQLite in the project folder, append-only by trigger; pictures stored under their content hash.
   - *Proof.* `reproduce` makes an observation again from its log entry alone, in a new session, and compares:
     the same frames by pixel hash, the same sound samples, the same picture byte for byte. It refuses a file
     whose content has changed.
   - *Decisions.* Pydantic AI as the host; Python run by Monty as what the model writes (section 5).
   - *Limits, on purpose.* One span per look. No transcript, shots or map yet, so long spans are sampled evenly
     in time. The picture is a PNG, which is exact but large. The frame index is read from packets without
     decoding, so a codec that stores frames it never shows fails the timestamp check and is not silently wrong.
1. **M1, the environment and a minimal explorer.** In progress.
   - *Done: cuts and the upper ladder.* Cuts are measured once per source and land on exact frames. A Section
     shows one frame per shot; a Map covers the whole source. The strip marks cuts.
   - *Done: the transcript.* Whisper, kept as an estimate with its model. Once a source is transcribed, a look
     writes under each frame the words said from that frame until the next, and marks words on the strip. There
     is no separate "pause between words" signal: pauses stay one measurement, from the sound.
   - *Done: real footage.* Six NASA videos (an interview, a briefing, an explainer, two action reels, a vertical
     short), fetched by a manifest with hashes (`bench/footage`). 21 draft locate tasks, written by a model from
     the transcript and the cuts, so **none can score a model until a person confirms it**.
   - *Done: the reading check* (`bench/reading`). Two models (Claude Sonnet 5.5 and GPT 5.6 Terra, through
     OpenRouter) each answered 20 questions three times on generated clips whose answers are known; each answer
     is checked against the log. All five kinds of question scored 12/12 for both: reading the grid in time
     order, the printed times, a scene change between neighbours, the sound strip against the ticks, and the
     boundary view. The picture format stays.
   - *What the check caught.* Asked for "the two consecutive frames" around a cut, GPT scored 0/12: it found
     the cut and answered in frame numbers of the video. "Frame" meant two things. Every observation now says
     that a number means a picture on the sheet.
   - *Words: under the pictures, in the text, or both.* On real footage, "which picture is on screen when this
     word is said" scored 24/24 for both models all three ways, so that question does not separate them. Text
     only used about a fifth fewer input tokens than both. The default stays both until a question that needs
     word and picture together is measured.
   - *What it cost on real footage* (CPU, no GPU): a 19-minute interview took 291 s to transcribe and 18 s to
     scan for cuts, once. Six looks on real files were made again exactly in 14 s.
   - *Found and fixed on the way.* Signals were measured on a timeline shifted by the file's start time, so on
     a file that does not start at zero a pause was drawn in the wrong place. They now keep the file's own
     timestamps.
   - *Done: the library* (`uberseek/api`). Thirteen operations that return plain values: `find`, `words`,
     `pauses`, `loudness`, `cuts`, `shots`, `observe`, `observations`, `coverage`, `info`, and span arithmetic
     (`expand`, `merge`, `minus`). An agent may use only the videos it is given, by name.
   - *Done: `find` over the transcript.* Passages are cut at sentence ends and where the speaker stops, and
     ranked by the words they share with the query. **It matches words, not meaning**: a paraphrase finds
     nothing. `find(like=...)` says plainly that the picture index is not built.
   - *Done: the executor* (`uberseek/exec`). A program runs in Monty with the library as its only way out, under
     limits on time, memory, library calls, looks per program and the size of what comes back. An error returns
     with the line that caused it. Every run is logged with its calls. Pictures a program makes are handed to
     the model beside its result.
   - *Done: two surfaces in the host*, over the same library: `code` (`find`, `observe`, `execute`) and `tools`
     (one operation per call). The reference inside `execute` is generated from the library itself.
   - *Every picture now carries a title* with its video and span, so pictures from one program cannot be mixed
     up.
   - *Tried with real models, not measured.* One spoken and one picture-only locate task, two cheap models
     (Claude Haiku 5.5, GPT 5.6 Luna), both surfaces: every run finished and named a span. Single runs varied,
     and the code surface used two to three times the tokens on the picture task. That is what E6 measures;
     nothing here decides it.
   - *What the trial exposed.* A draft label was wrong: the cut detector missed a flash to white, so "the shot"
     began two seconds early. Looking at the picture showed it. Cut detection misses flashes and dissolves, and
     draft labels do need a person.
   - *Done: the skill* (section 5), with a `guide` tool in the harness and `find`, `run`, `guide` and
     `skill install` on the command line. Writing its tests found a bug: `find(after=...)` past the end of a
     video raised an error where it should return nothing.
   - *Tried with and without the skill, not measured* (`bench/locate/results`). Four draft tasks, two cheap
     models, both surfaces, 32 runs. With the skill every run looked before answering (8 of 8 against 6 of 8)
     and one more task was found on each surface (7 of 8 against 6 of 8, within chance at this size). On the
     code surface it halved the programs written and cut tokens by a fifth; on the tools surface tokens rose,
     because the core is sent on every request. **It did not make these models combine steps in a program**:
     every program they wrote was a single call. That question stays open for E6 and for stronger models.
   - *A second wrong label.* The interview answers one question twice and the draft had one range. That is two
     wrong labels in four tasks tried.
   - *First run of E6 and E8 together* (`bench/compose/results`). Six tasks of the form "find A, then the
     related B", with answers computed by code; Claude Sonnet 5.5; both surfaces; 36 runs.
     - On the four sound tasks both surfaces were right 12 of 12. Composition was not the hard part.
     - Code used 29% fewer input tokens on average, and a third as many where there was much data to go through
       (counting a word across three minutes of speech). It used more on tasks that needed two lookups.
     - This model combined steps in half its programs; the cheap models never did.
     - Two tasks were flawed because their computed answers were wrong: a silence recorded as two that touch,
       and a missed cut. On the first, every program trusted the list and was wrong; the model on the tools
       surface read the list, joined the two, and was right. **A program trusts its data; a model that sees
       the data can notice it is wrong.** The silence measurement is fixed.
     - What follows: keep both, offer them as one surface (plain operations plus `execute`), and have programs
       return the runner-up and look at the winner. A computed answer is not ground truth.
   - *Done: `sheet`.* A program picks up to 24 instants and labels them; the harness draws them on one
     picture, which counts as one look. It is for scanning and comparing: one frame per shot, one per
     candidate. The frames are separate instants, so there is no sound strip and `coverage` lists a sheet apart.
     **This moves one decision from the harness to the caller:** the harness still sets the size of what is
     shown, but the program now chooses which frames. That is a step toward letting the model set fidelity,
     which section 2 names as an open tension.
   - *Done: worked examples in the core of the skill.* No run had ever opened the skill's references (`guide`
     was called 0 times in 16 runs), so the six most useful programs are now in the part that is always read.
   - *Tried again, not measured* (`bench/locate/results`): two picture tasks, two cheap models, 4 runs. Programs
     that combine steps went from 0 of 10 to 7 of 12, and every run used a sheet. **Tokens did not fall; they
     rose about 40%**: the core is longer, and the models used sheets as well as looks. Whether a sheet saves
     anything needs a task where it replaces several looks, and more runs.
   - *Next.* The explorer of E6: SAVE's loop reproduced twice on the same core, once with plain tools and once
     as code, on confirmed locate tasks. That settles the surface early. Picture search is added to `find` only
     after text search and the ladder are measured. No separate orchestration framework.
2. **M2, candidate comparison.** The brief and profile, the candidate set, the cheap measured signals, and
   `compare` with matched frames, sound strips and context. Preferences recorded with their context.
3. **M3, boundary comparison.** `mark` with alternative cut points shown as dense frames with the sound strip.
4. **M4, controlled experiments.** E0 to E5 of section 6: whether each added capability improves locating,
   choosing or trimming over its simpler baseline. E2 first, since it carries the research question.

Only after a gain is shown: robust adapters for many models, the second media backend, richer views of the state,
wide benchmark coverage.

## 8. What is new and what is not

- **Not new:** turning a requested time range into a view whose detail depends on the range. SAVE does this, with
  scene detection that adapts to the range and higher fidelity for narrow ranges, and it is the baseline to
  reproduce faithfully. Coarse-to-fine search (VideoTree, T\*), looking on demand (VIVID) and choosing what and
  where to observe (AVP) are also published.
- **Not new either:** choosing and trimming as tasks, with labels (`archive/` notes; verified against the papers
  except where marked).
  - *Learning to Cut by Watching Movies* (Pardo et al., ICCV 2021): ranks cut points between two shots, with
    sound; 257,064 cuts, labels taken from where films cut; scored within 0.33 to 1 s.
  - *Learning Where to Cut from Edited Videos* (Huang et al., ICCV 2021 workshops): predicts good start and end
    cut points. Read as an abstract only.
  - MEDit-Bench (arXiv:2607.25300): 60 videos, 3 messages, 3 professional editors, 540 edits with selected source
    ranges; sound ignored on purpose; best model below human agreement. Its model judge picks the human edit
    55.6% of the time when shown first and 20.2% when shown second.
  - RoughCut-Bench (arXiv:2611.24098): 1,476 highlight spans and transcript deletion spans; frames at 1 per
    second and transcripts, no raw sound; fixed pipelines, no agent choosing what to look at.
  - VEBench (arXiv:2605.03276): pick the right footage among four candidates, then give its start and end, with
    sound, in one model pass.
- **Programs in place of tool calls.** Cloudflare's Code Mode turns tools into a typed API the agent writes code
  against, run in a sandbox, so intermediate results stay out of the model's context; a later version reaches a
  very large API through two tools, a search and an execute. (From the articles the proposal cites; not re-read
  by us.) Their measured savings are for large tool catalogues. Nothing found applies this to video, where the
  open problem is getting what the footage looks and sounds like back to the model.
- **Harness engineering** (verified; OpenAI's post read as snippets only). A source-code study of eleven coding
  agents (arXiv:2609.00006) finds none uses a general agent framework and that a more elaborate loop "does not
  predict benchmark performance". Anthropic's guidance covers just-in-time context, clearing tool results, and
  durable handoff artifacts; one of its posts argues that a harness should not take decisions the model is better
  placed to make. Agentic Harness Engineering (arXiv:2604.25850) improves a harness from its own traces, but its
  headline gain is on the tasks it tuned on; on held-out tasks the gain is 0.4 points, and it predicts its own
  regressions poorly.
- **Selection biases and dimensions** (verified). AdShot (arXiv:2610.33377; 823 pairs of a 30 s advert and its
  15 s cut) finds models favour information-rich and emotional shots and under-select action and imagery, and six
  of its fifteen models score below a random baseline; its labels are automatic and it measures whole-shot
  keep-or-drop only. TRINITY (arXiv:2608.29577) splits highlight quality into several dimensions, for personal
  videos, with automatic labels and no brief.
- **Nearest work on each idea here.** Take selection for a stated style, by rules (Leake et al., 2017, read as a
  snippet); ranking learned from pairwise preferences, on whole edits with a model judge (Crayotter) or on user
  highlights (Video2GIF); agents that choose what to look at in video, for question answering, which stop when
  they have enough to answer (LensWalk, AVP, OmniAgent). Not found: these joined for an editorial choice, or a
  rule for looking tied to which pending choice it could change. The search was not exhaustive.
- **Ours to show:** an agent that controls its own looking under a budget; that looks further
  because a specific editorial choice is unresolved; comparison of several takes of the same content against a
  brief; in and out points chosen among alternatives to sub-second error, each with a reason. None of the works
  above tests these.

The ladder is an engineering choice. The claim is about comparison, and it stands only if section 6 shows it.

## 9. Later iterations

The same base, more modules. Research on each is in [archive/](https://github.com/prefix-tree/uberseek/tree/main/docs/archive); `research-validation.md` there says
where the evidence stands.

| Iteration | Capability | What the research says so far |
| --- | --- | --- |
| 1 (this document) | The base for exploring video, and the selection module | Sections 1 and 8 |
| 2 | Carrying out edits inside the harness, through UberScene (FFmpeg for what UberScene cannot do) | Typed, undoable timelines for agents exist (Cassette-Editor); whether typed actions beat editing the file as text is untested |
| 3 | Reviewing the result by watching and hearing the render | No one has compared a watching critic with a reading one; model judges are reliable on checkable items and weak on craft |
| 4 | Revisions: keeping approved material intact across notes | A code gate with rollback is the mechanism with evidence |
| Hearing | Real sound, and short clips, in `observe`, for models and hosts that can take them | Agents judging from stills and transcripts cannot assess delivery or rhythm; this is the known cost of images only |
| Other modules | Question answering, search, compliance review (which needs evidence of absence), action analysis | The base serves them without change; each needs its own module |
| Later | Live streams; a fast decision model; training on the harness's own traces | In the archive |

Each is added only after the one before it has shown its value in an experiment.

## 10. Open questions, with the current recommendation

| Question | Recommendation |
| --- | --- |
| Which host harness? | Decided: Pydantic AI (section 5) |
| Which language does the model write? | Decided: Python, run by Monty (section 5). M1 measures how often models write outside Monty's subset |
| Does a real model read the pictures well? | Yes on generated clips: 12/12 on five kinds of question for two models (section 7, `bench/reading/results`). Not yet measured on hard real footage |
| Where do the words go? | Open. Under the pictures, in the text and both all read correctly; text is cheapest. Needs a question where word and picture must be judged together |
| Who confirms the locate tasks? | Open. The 21 drafts need a person to watch each one; until then they are not ground truth |
| PNG or JPEG for what is shown? | PNG for now: exact and reproducible, but large. Measure the size on real footage before changing |
| Which models first? | Two strong models that take images and tool calls, from different providers, to see whether results hold across models |
| Which footage? | Interviews and action-heavy material. Reuse labelled editing sets where licences allow; label a small set of candidate pairs and boundaries ourselves |
| Very long sources | One cheap map to start, refined in parts and cached. Measure where it fails before adding more |
| How is `purpose` given? | Free text, with an optional link to a line of a brief. No fixed taxonomy yet |
| Who are the editors for blind preference? | Open. Without them, choose and trim have only code-scored measures |
