# UberLens: design

UberLens is an agent harness for video, the way OpenCode is one for code. It does one job: **pick the right
time**. Given footage and what is needed, it finds the moment, chooses the best candidate, and sets exactly where
it starts and ends.

It works by **zooming**: from the whole video down to a single frame, narrowing at each step. The harness, not
the model, decides how each step is shown.

UberLens does not edit. It hands its selections to whatever does: UberScene, FFmpeg, another agent.

This is the one maintained document. Everything earlier (the research reports, the activity-prior notes, the
previous design) is frozen in [archive/](archive) and is cited here by file name where a number comes from it.

## 1. The problem is picking, not executing

- **Executing works.** On Timeline-Bench, 857 of 863 agent videos met the delivery spec and most passed every
  brief test. Only 14% of runs were resolved, because 562 of 771 failures were on quality alone
  (`research-validation.md`).
- **Picking fails.** Agents there cut 0.72 times as often as editors, and only 5.5% of their own fixes concern
  pacing, story or shot choice, against 66% of editors' notes. On AgenticVBench, 65% of failed repairs looked in
  the wrong time window.
- **Models answer right while pointing at the wrong moment.** On NExT-GQA, 69% of answers are right but only 16%
  are right with the right evidence.
- **Agents see stills and transcripts.** That can show what is in a shot. It cannot show delivery, rhythm, or the
  instant an action lands, which is what choosing and trimming depend on.

Picking has three levels, and the research covers them unevenly:

| Level | Question | State of the art |
| --- | --- | --- |
| **Locate** | Where in the footage is what I need? | Heavily studied (SAVE, ForeSeek, T\*, VideoTree) |
| **Choose** | Of several candidates, which is best for this purpose? | Barely studied |
| **Trim** | Exactly where does it start and end? | Barely studied |

UberLens covers all three. Choose and trim are where it can add something new.

## 2. The zoom ladder

The agent never asks for frames. It asks to see a **span of time**, and the harness renders the view that fits
the span's width.

| Level | Span | What the agent is shown | What it decides |
| --- | --- | --- | --- |
| **Map** | The whole source | One strip: a frame per section, the sound wave, where speech, silence and cuts are | Which regions to open |
| **Section** | Minutes | One frame per shot, with the gist of what is said | Which shots or passages are candidates |
| **Passage** | 10–60 s | A frame every second or two, with the words | Which candidate is best |
| **Moment** | 1–8 s | A dense run of frames with the real sound | Where it starts and ends |
| **Frame** | One instant | Full resolution, or a crop | Detail: a face, a sign, focus |

**The harness sets the view.** How many frames, at what size, with or without sound, follows from the span's
width, by a fixed table. In SAVE, a harness rule for density and resolution beat the model's own choice by 3.7 to
5.8 points, and a range explorer of this kind matched full-video inference at 40% of the cost on its main
benchmark and beat it by 8.8 points on videos of 15 minutes or more (`research-rres.md`). Starting values are
SAVE's (6 frames up to 10 s, 12 up to 60 s, 25 up to 8 minutes), with full resolution only at the bottom two
levels.

**Every view states what it shows:** the span, the timestamps actually decoded, the gap between samples, the size
of each frame. A view that could not have shown a short event says so.

### Actions

| Action | Does |
| --- | --- |
| `zoom(span)` | Opens a span one level down |
| `back` | Returns to the level above |
| `find(text)` | Searches the transcript and jumps to matching passages (speech footage) |
| `compare(a, b)` | Shows two candidates side by side, at the same level |
| `mark(span, purpose, why)` | Selects a range with its in and out points |
| `done` | Ends, with the selections and what was not opened |

### What the harness enforces

A plugin only adds tools; the model can ignore them or misuse them. A harness owns the loop, so the ladder is a
rule and not advice:

- No full-resolution view of a wide span; detail is reached by descending.
- A `mark` needs in and out points that were seen at the moment level, or it is recorded as rough.
- Views leave the model's context after each step. The tree of what was opened stays (section 4).
- A budget of views, tokens and time per task, counted and capped.

### Building the map

The map and the sections are built once per source, by code, and cached by the file's content hash:

- **Shots and sections** from cut detection.
- **Sound**: loudness, speech and silence.
- **Transcript** with word timings, for footage with speech. On speech-heavy video a transcript alone carries
  most of the locating: on Video-MME long with a 7B model, subtitles score 65.4 and frames 52.0
  (`research-validation.md`). So `find` is the first move there, and looking is for what words cannot show.
- **Activity marks** (bitrate and keyframes read from the file, about 0.07 s per minute of video) drawn on the
  map as hints. They are unproven and are tested against a plain map (section 6).

Cold-start cost is reported separately from the cost of each task.

## 3. What comes out

A list of **selections**:

```python
class Selection(BaseModel):
    source: str               # content hash of the file
    start: float              # seconds, the in point
    end: float                # the out point
    purpose: str              # what it is for: a slot, a question, a brief line
    why: str                  # the agent's reason
    alternates: list[str]     # other candidates for the same purpose, ranked
    seen_at: Literal["moment", "passage", "section"]   # the finest level its in and out points were seen at
    trace: list[str]          # the views that led to it
```

Exporters turn selections into what an editor needs: JSON, a cut list (EDL), FFmpeg commands, or an UberScene
file. Editing itself is out of scope.

## 4. State

Everything lives outside the model's context, in the project folder, so a task survives a full context or a new
session and can continue with another model.

- **The tree.** Each opened span is a node: its level, the exact view shown (stored by content hash), the
  timestamps decoded, the model call that saw it. The tree is the record of what was looked at and how closely,
  and it is the cost record.
- **Selections**, as above.
- **The log** of every action and its options.

The tree proves what was **shown**. It does not prove the model read it correctly: models cite the right moment
for the wrong reason often, and citing alone does not make answers more correct (`research-validation.md`).
Correctness is only measured against labels or checked by something independent.

## 5. The harness

- **Its own loop**, model-agnostic. Each model gets a short contract: tool calling, images, and whether it takes
  audio or video directly. Where a model cannot hear, the moment level falls back to frames plus words and
  loudness, and that weaker view is recorded.
- **A core library** (the ladder, the views, the tree) with a thin runner on top. The same library is exposed as
  tools, so the ladder can also be used inside OpenCode or Claude Code.
- **Python**; media through FFmpeg and PyAV; transcription with Whisper.

```
uberlens/
  ladder/     # levels, the view table, zoom / back / find / compare / mark
  views/      # rendering: strips, sheets, bursts, sound, crops
  ingest/     # content hash, shots, sound, transcript, activity marks
  state/      # tree, selections, log, budget
  runner/     # the agent loop, model adapters
  export/     # JSON, EDL, FFmpeg, UberScene
  server/     # the same actions as tools (MCP, CLI)
bench/        # tasks, scoring, cost report
```

## 6. Proof

One question per experiment, the same model in every arm, matched budgets, repeated runs.

**Arms**

| Arm | What it has |
| --- | --- |
| Transcript only | The words and their timings, no looking |
| Plain frame tools | "Give me N frames from this span", density chosen by the model |
| Range explorer | SAVE's loop, written from the paper |
| **UberLens** | The ladder |
| Full-video inference | The model watches the video, where it can |

**Measures**

| Level | Measure |
| --- | --- |
| Locate | Does the marked range overlap the labelled one |
| Choose | Was the labelled best candidate picked among the alternatives |
| Trim | Error of the in and out points, in seconds |
| Downstream | With a fixed editor, is the cut better: the right shot per slot (AgenticVBench's assembly tasks) |
| Cost | Views, tokens, money and time, cold start and per task |

**Data.** Locate has public sets with labelled moments (LV-Haystack from LongVideoBench; AgentVidBench), all with
licence limits recorded in `research-validation.md`. Nothing public labels choose or trim, so UberLens needs a
small set of its own on footage it may redistribute, with several takes of the same thing and hand-marked in and
out points. That set is the new part of the benchmark.

**Size.** Small sets only show large effects: 20 tasks with 5 runs each detect about 17 points, 56 tasks with 5
runs about 10 (arithmetic under worst-case run noise, `research-validation.md`). The first run is a pilot that
measures the real variance.

**What would make us drop a part**

| Part | Dropped or simplified when |
| --- | --- |
| The ladder as a whole | It does not beat the range explorer at equal cost |
| Looking, on speech footage | Transcript only matches it; then looking becomes an escalation for what words cannot show |
| The moment level with sound | It does not improve choose or trim over frames and words |
| Activity marks on the map | A plain map does as well |
| `compare` | Side-by-side choices are no better than one at a time (pairwise judgments flip with order in other studies) |

## 7. Milestones

0. **M0, ground.** Pick the first models and write their contracts. Check the licences of the locate sets.
   Collect and label the first choose-and-trim footage.
1. **M1, the ladder.** Ingest, the five views, the view table, the tree, the actions, the runner. Tested on
   synthetic videos with known events.
2. **M2, locate.** The arms of section 6 on labelled moments; the variance pilot.
3. **M3, choose and trim.** `compare`, the moment level with sound, the own set.
4. **M4, downstream.** Exporters, and a fixed editor on assembly tasks to show that better picking gives a better
   cut.

## 8. What is new and what is not

- **Not new:** coarse-to-fine search (VideoTree, T\*), a range explorer with harness-set density (SAVE, the
  closest work), looking on demand (VIVID), choosing what and where to observe (AVP).
- **Ours to show:** a fixed ladder the harness enforces down to the moment with sound; choose and trim as
  measured targets, with data for them; selection as a product separate from the editor, usable by any of them.

The claim is empirical. It stands only if the experiments of section 6 show it.

## 9. Left out, and where it went

Editing through typed actions, the critic, editorial passes and approvals, claim kinds, the belief scheduler,
streaming and training are not part of this design. The research on each is in [archive/](archive);
`research-validation.md` there says where each one stands and what the audit of UberScene found.

## 10. Open questions

1. Which models first, and which of them can hear?
2. Which footage for the choose-and-trim set, and who marks it?
3. Does the map need one image per source, or a few for very long sources?
4. How `purpose` is given: a free line, or slots from a storyboard or brief.
