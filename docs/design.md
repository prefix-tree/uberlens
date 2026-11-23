# UberLens: design

UberLens is an agent harness for video, the way OpenCode is one for code: one reusable harness that brings
together what an agent needs to work with video, with its own loop, for any model.

It has two layers:

- **A base for exploring video.** Sources, observations, navigation, cost and task completion. It knows nothing
  about editing. Anything that needs to look at video can be built on it: question answering, search, review,
  selection.
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
| **Choose** | Of several candidates, which is best for this purpose? | Studied as ranking and highlight selection; see below |
| **Trim** | Exactly where does it start and end? | Studied as cut-point prediction; see below |

Choose and trim have prior work (cut placement learned from edited videos; benchmarks of selection and trimming
named in section 8, being verified). What is not yet evaluated, as far as we have found, is a general agent that
**compares candidates directly, with picture and sound and their surrounding context, under one observation
budget, and justifies each boundary**. That is the gap this iteration aims at.

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

### Navigation

| Action | Does |
| --- | --- |
| `zoom(span, focus)` | Shows a span, in the form that fits `focus` |
| `back` | Returns to the wider view |
| `find(text)` | Searches the transcript and jumps to matching passages |
| `done` | Ends the task, with what was not looked at |

`focus` says what the look is for:

| Focus | The harness shows |
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

- **The harness sets fidelity; the agent sets extent and focus.** In SAVE, a harness rule for frame count and
  resolution beat the model's own choice by 3.7 to 5.8 points (`research-rres.md`). `focus` is a category, not a
  frame count, so that finding still holds here.
- **Caps**, whatever the focus: frames per view, pixels, seconds of sound, and a budget of views, tokens and time
  per task. The model never writes media commands.
- **Every observation states what it delivered:** the span asked for, the presentation timestamps actually
  decoded, the gap between samples, frame size, whether sound was included.
- **Degraded is not equivalent.** If a model cannot hear, a `delivery` or `boundary` look returns frames, words
  and loudness, and is recorded as **degraded**. Anything decided from it that depends on sound (hesitation,
  clarity under music, the rhythm of a cut) is marked unverified. Results are reported separately for models that
  can hear and models that cannot, since they are doing different tasks.
- **Observations leave the model's context** after each step; the log stays (section 4).

### Built once per source

By code, cached by the file's content hash: shots, loudness, speech and silence, and for speech footage a
transcript with word timings. On speech-heavy video a transcript alone carries most of the locating (on
Video-MME long with a 7B model, subtitles score 65.4 and frames 52.0, `research-validation.md`), so `find` is the
first move there. Activity marks from bitrate and keyframes can be drawn on the map; they are unproven and tested
against a plain map. Cold-start cost is reported separately from the cost of each task.

## 3. The selection module

Two actions on top of the base.

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
    purpose: str                 # free text, optionally tied to a line of a brief
    why: str
    alternates: list[str]        # other candidates considered, ranked
    start_status: Literal["rough", "compared", "unverified"]   # unverified: decided from a degraded look
    end_status: Literal["rough", "compared", "unverified"]
    observations: list[str]      # the observations it rests on
```

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
- **Selections**, as above.
- **Cost**, per observation and per task.

**Time.** Positions are kept as presentation timestamps in the media's own timebase (a rational number), not as
floating-point seconds, so variable frame rate and audio alignment do not move a cut.

The log proves what the model was **shown**, not that it read it correctly. Correctness is only measured against
labels or checked by something independent (`research-validation.md`).

## 5. The harness

Kept thin until the method has shown a gain. The first build is a small loop and the pieces below, not a
framework.

- **The loop.** Task, observations, actions, budget, state. Model-agnostic.
- **Model contract.** What each model can take: tool calls, images, sound, video. A missing capability is a
  recorded restriction (section 2), not a silent fallback.
- **Media, behind one interface.** FFmpeg is the reference implementation and an inner tool of the harness.
  FilmCraft's codecs (through `uberscene-codec`) are an optional second implementation, to be used only after it
  matches FFmpeg on: the frame returned for a requested timestamp, variable-frame-rate seeking, sound and picture
  sync, colour conversion, behaviour around keyframes, and damaged files. What the model sees must be identical
  across backends in any experiment.
- **Python**, Whisper for transcription.
- **Tool surface.** The same actions can be exposed as tools for use inside OpenCode or Claude Code.

```
uberlens/
  media/        # the media interface; FFmpeg reference, uberscene-codec optional
  ingest/       # content hash, shots, sound, transcript, activity marks
  observe/      # the observation policy: focus, ladder defaults, caps, rendering
  state/        # observation log, cost
  loop/         # the agent loop, model contracts
  select/       # the selection module: compare, mark, selections, export
bench/          # tasks, scoring, cost report
```

## 6. Proof

**The research question.** Can an agent that directly compares candidate video moments, with their surrounding
picture and sound, select and trim better footage than an agent that retrieves and ranks the same candidates one
by one?

It is distinct from SAVE, which settles how to locate. If it fails, the ladder may still be a useful interface,
but there is no new method.

Three questions, each with its own data, because a system can be good at one and poor at another:

| Question | Compared | Primary measure |
| --- | --- | --- |
| Does adaptive exploration help **locate**? | Full-video inference; a static index (transcript and shot captions); SAVE, reproduced faithfully; UberLens | Localization accuracy at equal total cost |
| Does comparison improve **choosing**? | Ranking candidates independently vs `compare` | Blind editor preference; usefulness of the chosen candidate |
| Does boundary comparison improve **trimming**? | Transcript boundaries; silence-based boundaries; boundary comparison | Blind preference between boundaries; speech left intact; time error where one answer exists |

Rules for all three:

- The same model in every arm, matched budgets with reasoning tokens counted, repeated runs.
- `compare` is ablated on its own, so a gain over SAVE can be traced to the ladder, to comparison, or to more
  reasoning.
- Results for models that can hear are separate from those that cannot.
- Full-video inference is always an arm: where evidence is not sparse it can make exploration unnecessary.
- Human cut points are not treated as the only right answer; several professional edits of the same material
  differ.

**Data.** Locate has public sets with labelled moments. For choose and trim, existing sets are reused where their
licences allow (section 8, being verified), and a small set is labelled for what they lack: pairs of candidates
with a preferred one, and boundaries with acceptable alternatives. Footage is interviews plus action-heavy
material.

**Size.** Small sets only show large effects: 20 tasks with 5 runs each detect about 17 points, 56 tasks with 5
runs about 10 (arithmetic under worst-case run noise, `research-validation.md`). The first run is a pilot that
measures the real variance.

**What would make us drop a part**

| Part | Dropped or simplified when |
| --- | --- |
| The ladder | It does not beat SAVE at equal cost; then SAVE's loop is the base |
| `focus` | Views chosen by focus do no better than the ladder's defaults |
| Looking, on speech footage | Transcript only matches it; looking becomes an escalation |
| `compare` | Direct comparison does no better than independent ranking, or its verdicts flip with order |
| Boundary comparison | It does no better than transcript or silence boundaries |
| Activity marks | A plain map does as well |

## 7. Milestones

One vertical experiment before a broad harness.

0. **M0, the observation contract.** FFmpeg-backed source reading: frames, sound, timestamps. The simplest
   persistent log. Proof that an observation can be reproduced exactly.
1. **M1, a minimal range explorer.** SAVE's loop reproduced with a small loop of our own, plus the ladder
   defaults and `focus`. No separate orchestration framework.
2. **M2, candidate comparison.** `compare` with matched picture and sound and context, and selection reasons tied
   to the brief.
3. **M3, boundary comparison.** `mark` with alternative cut points shown with real sound and dense frames.
4. **M4, controlled ablations.** Whether each added capability improves locating, choosing or trimming over its
   simpler baseline.

Only after a gain is shown: robust adapters for many models, the second media backend, richer views of the state,
wide benchmark coverage.

## 8. What is new and what is not

- **Not new:** turning a requested time range into a view whose detail depends on the range. SAVE does this, with
  scene detection that adapts to the range and higher fidelity for narrow ranges, and it is the baseline to
  reproduce faithfully. Coarse-to-fine search (VideoTree, T\*), looking on demand (VIVID) and choosing what and
  where to observe (AVP) are also published.
- **Not new either:** choosing and trimming as tasks. Named by a reviewer and being verified: cut placement
  learned from edited videos, MEDit-Bench (selection and sequencing for different editorial objectives, with
  several professional edits each), RoughCut-Bench (highlight selection, transcript-driven trimming), VEBench
  (candidate selection and temporal localization).
- **Ours to show:** direct, context-preserving comparison of candidates with picture and sound by a general agent;
  boundaries chosen among alternatives with a reason; both under one observation budget and one log.

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
| Which models first? | One strong model that takes sound and video, and one strong text-and-image model. The second runs with sound-dependent judgments marked unverified |
| Which footage? | Interviews and action-heavy material. Reuse labelled editing sets where licences allow; label a small set of candidate pairs and boundaries ourselves |
| Very long sources | One cheap map to start, refined in parts and cached. Measure where it fails before adding more |
| How is `purpose` given? | Free text, with an optional link to a line of a brief. No fixed taxonomy yet |
| Who are the editors for blind preference? | Open. Without them, choose and trim have only code-scored measures |
