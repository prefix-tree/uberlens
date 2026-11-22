# UberLens: design

UberLens is one video agent with two modes over the same tools and the same state:

- **Offline long-form** (ForeSeek-led): the whole video is available. The agent predicts what unseen stretches
  contain, checks the most promising ones, and uses failed predictions to rule stretches out.
- **Streaming** (ActiveForager-led): video arrives live. At each step the agent answers, looks closer at the recent
  window, recalls something from the past, or waits.

A fast System-1 model makes the many small choices (which interval next, which action, is this enough). The large
System-2 model is called only when System-1 is unsure, and to write the final answer.

Status: draft for review, no code yet. Python.

## 1. Sources

| Idea | Source | Used for |
| --- | --- | --- |
| Native perception tools (`get_frames`, `get_audio`, `get_clip`, `answer`), memory consolidation | OmniAgent | The tool set and the text memory |
| Short clean working window; Answer / ZoomIn / Recall / Wait; isolated Recall returning an EvidenceCard | ActiveForager (arXiv:2611.24267) | Streaming mode |
| Expectations over unseen intervals, global interval belief, failed expectations as negative evidence | ForeSeek (arXiv:2611.26024) | Offline mode, re-planning |
| Cheap calibrated decisions at enumerable choice points, escalate on low confidence | System-1 / AnyS1-style decision models | Every choice point in both loops |

These summaries come from the brief that started this project, not from reading the papers. Before building section
6 and 7, read both papers and correct anything here that disagrees with them (belief labels, window size, reward
terms).

## 2. Shared state

All state is plain, serialisable data (pydantic models). A run can be saved, replayed and diffed.

```python
class Span(BaseModel):
    start: float          # seconds
    end: float

class MemoryEntry(BaseModel):
    span: Span
    text: str             # what was seen/heard, distilled
    source: Literal["frames", "audio", "clip", "recall"]
    step: int

class Relevance(StrEnum):
    HIGH = "high"; MEDIUM = "medium"; LOW = "low"; ELIM = "elim"

class Interval(BaseModel):
    span: Span
    relevance: Relevance
    expectation: str | None     # what we predict is there, in words
    checked: bool = False
    evidence: list[int] = []    # MemoryEntry indexes that confirmed or refuted it

class AgentState(BaseModel):
    question: str
    mode: Literal["offline", "streaming"]
    memory: list[MemoryEntry]          # text only; raw media is dropped after consolidation
    window: list[Frame]                # streaming: ~4 most recent frames, low res
    belief: list[Interval]             # covers the whole known timeline, no overlaps
    archive: EventArchive | None       # streaming: past events Recall can search
    budget: Budget                     # frames, tool calls, System-2 calls, wall time left
    step: int
```

Invariants (checked in tests):

- `belief` partitions `[0, known_duration]`: sorted, no gaps, no overlaps. Splitting an interval keeps its label until
  updated.
- Raw media never enters `memory`; only the current step's observation carries pixels or audio.
- `budget` only goes down.

## 3. Tools

Same signatures in both modes; a mode just doesn't offer some of them.

| Tool | Args | Returns | Offline | Streaming |
| --- | --- | --- | --- | --- |
| `get_frames` | `span, n, res` | frames | yes | yes (past via archive) |
| `get_audio` | `span` | transcript + audio events | yes | yes |
| `get_clip` | `span, fps, res` | short dense clip | yes | yes |
| `seek_interval` | `interval_id` | observation of that interval, sampled to fit budget | yes | no |
| `zoom_in` | `res \| burst` | the recent window at high res, or a dense burst | no | yes |
| `recall` | `query` | `EvidenceCard` from a sub-agent | no | yes |
| `wait` | `seconds?` | nothing; the window advances | no | yes |
| `answer` | `text, confidence` | ends the run | yes | yes |

`update_belief` is not a tool the model calls freely: it is the step after every observation (section 6), so belief
always reflects what was seen.

**Recall sub-agent.** Runs with its own context over the archive and the memory, never adds to the main context
beyond its result:

```python
class EvidenceCard(BaseModel):
    query: str
    found: bool
    spans: list[Span]
    summary: str            # <= ~80 words
    confidence: float
```

**Media backend.** One `MediaSource` interface with two implementations: a file (ffmpeg/PyAV decode with a frame
cache) and a live stream (ring buffer; the archive keeps keyframes plus their captions). Tests use a synthetic video
with known content per second.

## 4. Offline loop (ForeSeek-led)

```
INIT ─► SKIM ─► PREDICT ─► PICK ─► OBSERVE ─► CONSOLIDATE ─► UPDATE ─► SUFFICIENT? ─yes─► ANSWER
                   ▲                                                  │
                   └──────────────── re-plan ◄─────── no ─────────────┘
```

1. **INIT**: belief is one interval `[0, duration]`, `MEDIUM`, no expectation.
2. **SKIM**: a sparse uniform pass (e.g. 1 frame per 2–5 min, plus audio transcript if cheap). Split the timeline
   at scene changes into ~10–30 intervals.
3. **PREDICT** (System-2, once per re-plan): for each unchecked interval, write an expectation tied to the question
   ("the receipt is shown at the counter, ~10:30–12:00") and a label.
4. **PICK** (System-1): choose the next interval. Candidates are unchecked `HIGH`, then `MEDIUM`.
5. **OBSERVE**: `seek_interval`, sampling to fit the frame budget; `get_audio` / `get_clip` if System-1 picks them.
6. **CONSOLIDATE**: distill the observation to a `MemoryEntry`; drop the pixels.
7. **UPDATE**: compare the observation with the interval's expectation.
   - Confirmed: keep `HIGH`; split around the matching part if it's narrower.
   - Refuted: the interval drops to `LOW` or `ELIM`. Neighbours whose expectation relied on the same assumption drop
     one level. If the refuted interval was the top `HIGH`, go back to PREDICT (global re-plan) with the failure
     written into the prompt as negative evidence.
   - Partial: split; label the parts separately.
8. **SUFFICIENT?** (System-1): is the evidence in memory enough to answer? Also stop when the budget is out or
   nothing `HIGH`/`MEDIUM` is left unchecked.
9. **ANSWER** (System-2): from memory only.

## 5. Streaming loop (ActiveForager-led)

At each tick (new frames arrived, or a timer):

```
TICK ─► DECIDE (System-1) ─┬─ Answer ─► emit, keep watching if the question is ongoing
                           ├─ ZoomIn ─► observe window at high res ─► CONSOLIDATE ─► DECIDE
                           ├─ Recall ─► sub-agent ─► EvidenceCard into memory ─► DECIDE
                           └─ Wait   ─► sleep until next tick
```

- The window holds ~4 recent frames at low res; it is replaced each tick, not appended.
- What leaves the window is captioned into the archive (cheap model, batched) so Recall can find it later.
- At most N non-Wait actions per tick, so a tick can't run away; then it Waits.
- Proactive questions ("tell me when the oven light goes off") Answer when the condition holds, not once.

The belief map exists here too but only over the past: Recall uses it to rank where to look, and its results update
it.

## 6. System-1

Every enumerable choice goes through one function:

```python
class Decision(BaseModel, Generic[T]):
    choice: T
    confidence: float           # calibrated probability that `choice` is right
    scores: dict[T, float]      # all options, for logging and calibration

def decide(point: DecisionPoint[T], state: AgentState) -> Decision[T]: ...
```

Decision points:

| Point | Options | Inputs | Escalate when |
| --- | --- | --- | --- |
| `next_interval` | unchecked interval ids | question, belief, last 3 memory entries | top-2 margin < τ |
| `observe_how` | frames / audio / clip, with density | question, interval expectation | confidence < τ |
| `stream_action` | answer / zoom_in / recall / wait | question, window captions, last memory | confidence < τ, or Answer below τ_answer |
| `sufficient` | yes / no | question, memory | confidence < τ |
| `verify_expectation` | confirmed / refuted / partial | expectation, observation summary | confidence < τ |

Escalation calls System-2 with the same inputs and options and the same output schema, so the loop doesn't care who
decided. Each decision is logged with who made it; these logs are the training data for a better System-1 later.

Backends behind one `DecisionModel` interface:

1. **Heuristic** (first build): label order, budget rules, keyword overlap. Deterministic, for tests and as a
   baseline.
2. **Small model**: a small VLM/LLM prompted for JSON with per-option scores; confidence from those scores,
   calibrated on logged decisions (temperature scaling).
3. **Distilled** (later): trained on System-2's escalated decisions.

τ starts at 0.7 and is tuned per point on a dev set for the accuracy/cost trade-off.

## 7. Models

Two interfaces, both provider-agnostic:

- `VisionLanguageModel`: `generate(messages, images, audio, schema) -> parsed output`. Used for System-2, captions,
  consolidation and the Recall sub-agent.
- `DecisionModel`: section 6.

Model choice is configuration, not code. The first build runs against one hosted VLM for System-2 and a small one for
captions and System-1; which ones is an open question (section 11).

## 8. Budget and stopping

`Budget` tracks frames decoded and sent, tool calls, System-2 calls, tokens and wall time. Every tool checks it before
running and refuses past the limit; the loop then goes to ANSWER with what it has and marks the answer
budget-limited.

## 9. Evaluation

- **Offline**: Video-MME (long split), LongVideoBench, MLVU, plus a small in-house set with timestamps.
- **Streaming**: OVO-Bench, StreamingBench; proactive-answer timing.
- **Metrics**: accuracy; frames sent per question (ForeSeek reports 2.5–4.4× fewer than search agents at equal
  accuracy; that is the bar); System-2 calls per question; System-1 escalation rate and calibration (ECE) per point;
  latency per tick (streaming).
- **Baselines** in the same harness: uniform sampling + one VLM call; reactive search (no PREDICT, no negative
  evidence); our loop with System-1 off (everything System-2).
- **Ablations**: no negative evidence; no re-plan; no consolidation; Recall in the main context instead of a
  sub-agent.

Every run writes a trace (state after each step, every decision, every tool call) that a small viewer can replay.

## 10. Training (later, not in the first build)

1. SFT on agent trajectories in the OmniAgent style, generated by the System-2-only loop and filtered for correct
   answers.
2. Add foresight trajectories: predict → verify → update belief.
3. RL (GSPO-style) with: correctness; ActiveForager's counterfactual information gain (a tool call is rewarded only
   if it raised P(correct)); a penalty per frame and per turn.
4. Distil the logged decision points into System-1.

## 11. Open questions

1. Which models for System-2, captions and System-1 to start? Hosted or open weights (open weights matter if we
   train)?
2. What is the first target use: a benchmark number, or a product question (e.g. finding moments in UberScene /
   Cutleap footage)? It decides which mode to build first.
3. Belief labels: four levels as ForeSeek has them, or a probability per interval with labels only for display?
4. Archive for streaming: captions only, or embeddings too for Recall search?
5. Budget defaults per mode (frames, seconds per tick).

## 12. Package layout and milestones

```
uberlens/
  state.py          # section 2 models and invariants
  media/            # MediaSource: file, stream, synthetic
  tools.py          # section 3
  belief.py         # split / update / negative evidence
  memory.py         # consolidation
  decide/           # DecisionModel: heuristic, small model, escalation
  models/           # VisionLanguageModel adapters
  loops/offline.py  # section 4
  loops/streaming.py
  recall.py         # sub-agent, EvidenceCard
  budget.py
  trace.py          # run traces + replay
eval/               # benchmark adapters, baselines, metrics
tests/
```

1. **M1, skeleton**: state, belief, budget, synthetic media, heuristic System-1, offline loop with a fake VLM.
   Tests cover invariants and a full run on the synthetic video.
2. **M2, real offline**: file media, a real VLM, consolidation, traces; first numbers on a small slice of Video-MME
   long against the baselines.
3. **M3, System-1**: small-model decisions with calibration and escalation; cost/accuracy curves over τ.
4. **M4, streaming**: window, archive, Recall sub-agent, Wait; OVO-Bench slice.
5. **M5, training**: trajectory export, SFT, then RL.
