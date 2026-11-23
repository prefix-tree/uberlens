# UberLens: design

UberLens is an agent harness for video, the way OpenCode is one for code: one reusable harness that brings
together what an agent needs to work with video, with its own loop, for any model.

It has two layers:

- **A base for exploring video.** A programmable environment: the agent writes small programs against a typed
  video API to search, measure and filter footage, and asks to be shown picture and sound only where a judgment
  needs it. Sources, observations, cost and task completion live here. It knows nothing about editing. Anything
  that needs to look at video can be built on it: question answering, search, review, selection.
- **Modules on top.** The first is **selection**: finding the moment that is needed, choosing the best candidate,
  and setting where it starts and ends.

It is built in iterations. The first iteration is the base plus the selection module. Later iterations add
carrying out edits, reviewing the result and handling revisions (section 9).

This is the one maintained document. Everything earlier (the research reports, the activity-prior notes, previous
designs) is frozen in [archive/](archive) and is cited here by file name where a number comes from it.

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
look at and listen to under a stated budget, compares several takes of the same content, sets in and out points
to sub-second error, and gives a reason for each boundary**. That is the gap this iteration aims at. Comparing
candidates with picture and sound is not new in itself (VEBench does it in one model pass, and the best model
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

Three primitives:

| Primitive | Does |
| --- | --- |
| `discover` | Returns the parts of the API relevant to the task, so the whole API never sits in context |
| `execute(program)` | Runs a bounded program against the API and returns its result |
| `observe(spans, focus)` | Delivers actual picture and sound to the model as an observation, by artifact id |

```ts
const source = await video.open("interview.mp4");
const hits = await source.transcript.search("company almost failed");
const candidates = await Promise.all(hits.map(async h => {
  const span = h.span.expand({ before: 5, after: 8 });
  return { span,
           words: await source.transcript.get(span),
           pauses: await source.signals.pauses(span),
           shots: await source.shots.in(span) };
}));
return candidates.filter(c => c.words.length > 0);
```

(Illustrative; the API does not exist yet.) The model then decides which of the returned candidates need to be
seen or heard, and asks for that with `observe`.

**Code computes; only the model perceives.** A program can search, measure, filter and rank on timings, words
and signals. It cannot judge delivery, framing or whether a cut lands. Any decision of that kind needs an
`observe`, and only what `observe` delivered counts as something the model saw or heard. How `observe` gets
picture, short clips and sound into the model's next step without flooding its context is the most important
design question of the base (section 10).

**The simple actions remain, as a library.** `zoom(span, focus)`, `back`, `find(text)` and `done` are functions
built on the same API, and can be exposed as plain tools for a model that does better with a small vocabulary.
Whether code beats those tools is an experiment (E6), not an assumption: writing and debugging programs costs
output tokens, and Code Mode's published savings are for very large tool catalogues, not for a handful of video
tools.

`focus` says what a look is for:

| Focus | `observe` delivers |
| --- | --- |
| `visual` (default) | Frames, by the ladder below |
| `speech` | The words with timings, and the sound; few or no frames |
| `motion` | Dense consecutive frames over a short stretch |
| `delivery` | Real sound with frames of the speaker |
| `boundary` | Frame-accurate picture and sound around one instant |

### The ladder: the default for `visual`

| Level | Span | What is shown |
| --- | --- | --- |
| **Map** | The whole source | One strip: a frame per section, the sound wave, where speech, silence and cuts are |
| **Section** | Minutes | One frame per shot, with the gist of what is said |
| **Passage** | 10–60 s | A frame every second or two, with the words |
| **Moment** | 1–8 s | A dense run of frames with the real sound |
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
  decoded, the gap between samples, frame size, whether sound was included.
- **Degraded is not equivalent.** If a model cannot hear, a `delivery` or `boundary` look returns frames, words
  and loudness, and is recorded as **degraded**. Anything decided from it that depends on sound (hesitation,
  clarity under music, the rhythm of a cut) is marked unverified. Results are reported separately for models that
  can hear and models that cannot, since they are doing different tasks.
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

- Each candidate is shown with picture and real sound, and with a little of what comes before and after it.
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
  end of a movement) and shows picture and sound around each.
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
    start_status: Literal["rough", "compared", "unverified"]   # unverified: decided from a degraded look
    end_status: Literal["rough", "compared", "unverified"]
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

- **An append-only observation log.** Each entry: the source and its content version; the span asked for and the
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

Kept thin until the method has shown a gain. The first build is a small loop and the pieces below, not a
framework. A harness is an engineered environment in which the model can make and check useful decisions, not a
bigger orchestration layer:

| Mechanism | In UberLens |
| --- | --- |
| Context kept small | Media and large outputs stay outside the model's context; only what the next decision needs is loaded |
| Durable state | Observations, candidates, selections and preferences persist across calls and sessions |
| A small surface | Three primitives (`discover`, `execute`, `observe`); the simple actions as a library on top |
| Checks before "done" | By code: selections play, source versions and timestamps are valid, constraints of the brief are met |
| Recovery | A long exploration resumes from the log |
| Delegation, only where isolation helps | Indexing and retrieval can run apart from the deciding model |
| Change by measurement | Harness changes are compared on held-out footage |

- **An environment first, a loop second.** The core is the typed video API, the bounded executor and the
  `observe` gateway. It is usable from an agent the user already has (Claude Code, Codex, OpenCode) through tool
  calls, and from a small loop of our own. The host model keeps the exploration strategy.
- **Model contract.** What each model can take: tool calls, images, sound, video, and whether its host can pass
  media back in a tool result. A missing capability is a recorded restriction (section 2), not a silent fallback.
- **Media, behind one interface.** FFmpeg is the reference implementation and an inner tool of the harness, run by
  trusted host-side services. FilmCraft's codecs (through `uberscene-codec`) are an optional second
  implementation, to be used only after it matches FFmpeg on: the frame returned for a requested timestamp,
  variable-frame-rate seeking, sound and picture sync, colour conversion, behaviour around keyframes, and damaged
  files. What the model sees must be identical across backends in any experiment.
- **Media services in Python**, Whisper for transcription. The language of the API the model writes against
  (TypeScript as in Code Mode, or Python) is open (section 10).

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
uberlens/
  media/        # host-side media services; FFmpeg reference, uberscene-codec optional
  ingest/       # content hash, shots, sound, transcript, signals
  api/          # the typed video API the model programs against
  exec/         # the sandboxed executor and its limits
  observe/      # the observe gateway: focus, ladder defaults, caps, rendering, delivery
  state/        # observation log, executions, cost
  actions/      # zoom, back, find, done as a library and as plain tools
  select/       # the selection module: compare, mark, selections, export
  loop/         # an optional small loop of our own, model contracts
bench/          # tasks, scoring, cost report
```

## 6. Proof

**The research question.** Can an agent make better editorial decisions by selectively acquiring picture and
sound evidence and comparing alternatives against an editorial objective, than by retrieving and ranking
candidates one by one?

The question is not whether the agent finds the most relevant moment. It is whether it can tell why one relevant
moment is editorially better than another, and what further look would help it decide. SAVE settles how to
locate; if this fails, the ladder may still be a useful interface, but there is no new method.

| | Experiment | Compared | Primary measure | Dropped when |
| --- | --- | --- | --- | --- |
| E0 | Does adaptive exploration help **locate**? | Full-video inference; a static index; SAVE, reproduced faithfully; UberLens | Localization accuracy at equal total cost | It does not beat SAVE; then SAVE's loop is the base |
| E1 | Do **signals** improve selection? | Excerpts alone vs excerpts plus selected speech, motion and semantic signals | Blind editor preference; observation cost | Signals improve neither |
| E2 | Does **direct comparison** beat independent ranking? | Absolute scores; pairwise audiovisual comparison; ranking several at once; same candidates, context and budget, order randomised | Blind editor preference | Comparison is no better, or its verdicts flip with order |
| E3 | Does the **brief** change which moments are right? | General relevance ranking vs ranking conditioned on the brief, same footage under several briefs | Agreement with editors working to each brief | Conditioning adds nothing over relevance |
| E4 | Does **decision-led looking** beat the alternatives? | Free inspection (VIVID-style); SAVE; the ladder; the decision loop of section 3 | Editor preference, missed alternatives, cost, share of looks that changed a decision | It is no better than plain range exploration |
| E6 | Does **code** beat plain tools? | A: plain tools (`find`, `zoom`, `compare`, `mark`); B: the API through `execute` only; C: `execute` plus `observe` | Accuracy on locate, choose and trim; tokens in and out; round trips; wall time; failed or invalid programs | The model spends more writing and fixing programs than it saves; then plain tools are the surface |
| E5 | Does **boundary comparison** improve trimming? | Transcript boundaries; silence boundaries; boundary comparison | Blind preference between boundaries; speech left intact | It does no better than the simple boundaries |

Rules for all of them:

- The same model in every arm, matched budgets with reasoning tokens counted, repeated runs.
- `compare` is ablated on its own, so a gain over SAVE can be traced to the ladder, to comparison, or to more
  reasoning.
- Results for models that can hear are separate from those that cannot.
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

## 7. Milestones

One vertical experiment before a broad harness.

0. **M0, the observation contract.** FFmpeg-backed media services: frames, sound, timestamps. The simplest
   persistent log. Proof that an observation can be reproduced exactly. Decide the API language and the sandbox.
1. **M1, the environment and a minimal explorer.** The typed API, the bounded executor and `observe`. SAVE's
   loop reproduced twice on the same core, once with plain tools and once as code, which is experiment E6 and
   settles the surface early. No separate orchestration framework.
2. **M2, candidate comparison.** The brief and profile, the candidate set, the cheap measured signals, and
   `compare` with matched picture and sound and context. Preferences recorded with their context.
3. **M3, boundary comparison.** `mark` with alternative cut points shown with real sound and dense frames.
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
  open problem is getting picture and sound back to the model.
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
- **Ours to show:** an agent that controls its own looking and listening under a budget; that looks further
  because a specific editorial choice is unresolved; comparison of several takes of the same content against a
  brief; in and out points chosen among alternatives to sub-second error, each with a reason. None of the works
  above tests these.

The ladder is an engineering choice. The claim is about comparison, and it stands only if section 6 shows it.

## 9. Later iterations

The same base, more modules. Research on each is in [archive/](archive); `research-validation.md` there says
where the evidence stands.

| Iteration | Capability | What the research says so far |
| --- | --- | --- |
| 1 (this document) | The base for exploring video, and the selection module | Sections 1 and 8 |
| 2 | Carrying out edits inside the harness, through UberScene (FFmpeg for what UberScene cannot do) | Typed, undoable timelines for agents exist (Cassette-Editor); whether typed actions beat editing the file as text is untested |
| 3 | Reviewing the result by watching and hearing the render | No one has compared a watching critic with a reading one; model judges are reliable on checkable items and weak on craft |
| 4 | Revisions: keeping approved material intact across notes | A code gate with rollback is the mechanism with evidence |
| Other modules | Question answering, search, compliance review (which needs evidence of absence), action analysis | The base serves them without change; each needs its own module |
| Later | Live streams; a fast decision model; training on the harness's own traces | In the archive |

Each is added only after the one before it has shown its value in an experiment.

## 10. Open questions, with the current recommendation

| Question | Recommendation |
| --- | --- |
| How does `observe` deliver media? | Open, and the most important one. As contact sheets and short sound clips returned by artifact id, sized by focus. It depends on what each host lets a tool result carry: images widely, sound and video rarely |
| Which language does the model write? | TypeScript in an isolate, as Code Mode does, or Python in a restricted process. Decide in M0 on which is easier to isolate and which the models write more reliably |
| Which models first? | One strong model that takes sound and video, and one strong text-and-image model. The second runs with sound-dependent judgments marked unverified |
| Which footage? | Interviews and action-heavy material. Reuse labelled editing sets where licences allow; label a small set of candidate pairs and boundaries ourselves |
| Very long sources | One cheap map to start, refined in parts and cached. Measure where it fails before adding more |
| How is `purpose` given? | Free text, with an optional link to a line of a brief. No fixed taxonomy yet |
| Who are the editors for blind preference? | Open. Without them, choose and trim have only code-scored measures |
