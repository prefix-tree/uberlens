# Activity prior: where to look first

**Status: UberLens extension.** No source paper does this (see [research.md](research.md)). It ships only if it
beats ForeSeek's uniform skim at the same frame budget (section 9); otherwise it is removed.

In [design.md](design.md) the profile is one of the layers built once per source (5.1), and it places half of the
`overview` tool's first look (5.2). The first version uses sections 3 to 5.2 and 5.4 here; question matching,
features for a fast scorer and streaming come later.

## 1. The problem: every source starts blind

Before the agent has seen anything, it has no idea where the answer is. Each source handles that first step the
same way, by spreading frames evenly:

- **ForeSeek** skims N(T) = clip(round(10 + 3·log2(1 + T/600)), 10, 20) evenly spaced frames, and its first
  intervals are the gaps between them ([research.md, ForeSeek](research.md#foreseek-one-expectation-a-label-belief-and-a-round-decay-reward)).
- **OmniAgent** tells the model to "scan wide first, then bisect", with no signal about where to scan.
- **ActiveForager** splits its archive by colour-histogram change, but only for frames it has already decoded.

A uniform skim gives equal attention to ten minutes of an empty corridor and to the ten seconds where someone walks
through it. ForeSeek's own numbers show the cost: frame use barely grows with video length (22 frames at 1 minute,
29.5 at 40 minutes) and accuracy falls on long videos. The first look decides where everything after it goes, and
it is made with no information.

## 2. The idea

A video file already says where things happen, before a single frame is decoded:

- the encoder spends more bytes where the picture changes, so **bitrate over time** is a free motion and change
  curve;
- encoders usually put a **keyframe** at a scene cut;
- the **audio track** shows speech, music and sudden sounds, and decoding audio alone is cheap;
- containers may carry **chapters** and **subtitle cues** with timestamps.

UberLens reads these cheap signals first, builds an **activity profile** of the whole video, and uses it to decide
where the first frames go, where the first intervals start and end, and, in streaming, when to stop waiting. Half
of the first look stays uniform, so the agent never relies on the profile alone: what is busy is not always what
the question is about.

## 3. Signals

All signals are computed once per video into one profile on a fixed time grid (default 1 s bins).

| # | Signal | How it is read | Cost (decode) | What a peak suggests | When it lies |
| --- | --- | --- | --- | --- | --- |
| S1 | Video bitrate | Sum of video packet sizes per bin, from the container (`ffprobe -show_packets` or PyAV demux without decode) | None | Motion, change, a cut | Constant-bitrate encodes (flat); heavy re-encodes (smoothed); noise and grain (high everywhere) |
| S2 | Keyframes | Packets flagged as keyframes; a keyframe off the regular GOP interval is a likely cut | None | Scene cut | Fixed-GOP encodes, common for streaming and web video, put keyframes on a timer |
| S3 | Audio energy | RMS loudness per bin from decoded audio | Audio only | Something happening, music, a bang | Constant music or noise under everything |
| S4 | Speech | Voice activity per bin from a small voice-activity model on decoded audio | Audio only | Someone talking | Silent videos; speech that is irrelevant (narration over everything) |
| S5 | Visual change | Distance between colour histograms of consecutive tiny frames (64 px wide, keyframes only or 1 fps), the descriptor ActiveForager uses for its archive | Low: tiny frames | Cut or large change | Slow changes; camera shake |
| S6 | Container metadata | Chapter marks; subtitle cue start times and density | None | Topic boundaries; dialogue | Usually absent on benchmark videos |
| S7 | Motion vectors (later) | Motion vectors exported while decoding (FFmpeg `+export_mvs`) | Partial decode | Where and how much things move | Codec-specific; skip in M1 |

S1, S2 and S6 need no decoding at all. S3 and S4 decode only audio. S5 decodes tiny frames. All of them together
should cost far less than one vision-model call on the same video (target in section 7).

### Reliability checks

Each signal is checked on the video itself and switched off when it carries no information:

- **S1 off** when the bitrate is flat: its coefficient of variation across bins is below 0.15 (a constant-bitrate
  encode).
- **S2 as a cut signal**: estimate the keyframe timer (the most common gap between keyframes) and treat keyframes
  off that grid as cuts. Switch S2 off when every keyframe sits on the grid (gap CV below 0.05), as in fixed-GOP
  encodes. See the measurement in section 7.
- **S3 and S4 off** when the video has no audio track, or audio energy is flat (same 0.15 rule).
- **S5** is the fallback for cuts when S2 is off.

The thresholds are starting values, tuned on a dev set in M2. The profile records which signals were used, so a
trace shows why the skim landed where it did.

## 4. Building the profile

1. **Bin** each signal on the 1 s grid.
2. **Normalise per video.** Video A's quiet is video B's loud, so each signal is turned into a robust z-score
   against its own median and median absolute deviation: z = (x − median) / (1.4826 · MAD). This also absorbs most
   of the difference between encoders.
3. **Smooth** with a short window (3 bins) so single-packet spikes don't dominate.
4. **Combine** into one activity curve a(t) = Σ wᵢ · max(zᵢ(t), 0) over the signals that passed the reliability
   check. Default weights: bitrate 1.0, visual change 1.0, audio energy 0.5, speech 0.5. Weights are changed per
   question by the profile choice in section 5.6.
5. **Cuts**: the set of times from off-grid keyframes (S2), visual-change peaks above 3 MAD (S5), and chapter marks
   (S6), merged when closer than 2 s.

```python
@dataclass(frozen=True)
class ActivityProfile:
    duration: float
    bin_sec: float                        # 1.0
    signals: dict[str, np.ndarray]        # raw per-bin values: "bitrate", "audio_rms", "speech", "visual_change"
    z: dict[str, np.ndarray]              # normalised, smoothed
    used: dict[str, bool]                 # result of the reliability checks
    cuts: list[float]                     # seconds
    chapters: list[tuple[float, str]]     # from the container, if any

    def activity(self, weights: Mapping[str, float]) -> np.ndarray: ...
    def summary(self, span: Span) -> IntervalActivity: ...   # section 5.3

def probe(source: MediaSource, *, decode_audio: bool = True, thumbs: bool = True) -> ActivityProfile: ...
```

The profile is plain data: it is saved with the run trace and cached per file (key: path, size, modification time).

## 5. How the agent uses it

### 5.1 The first skim (offline)

The number of skim frames stays ForeSeek's N(T), so comparisons are at equal budget. They are split:

- **⌈N/2⌉ uniform frames**, placed as ForeSeek places them. This keeps coverage, including the static stretches
  where the profile sees nothing (a whiteboard, a sign, a face).
- **⌊N/2⌋ activity frames**, at the highest peaks of a(t), at least T / (2N) apart from each other and from the
  uniform frames, so they don't cluster on one busy scene.

If no signal passes its reliability check, all N frames are uniform: the prior falls back to ForeSeek exactly.

The mix ratio is a parameter (`prior_mix`, default 0.5; 0 means pure ForeSeek), and section 9 tests it.

### 5.2 The first intervals

ForeSeek's first intervals are the gaps between skim frames. With the prior, interval boundaries snap to the
nearest cut within a quarter of the gap, so an interval tends to hold one scene instead of the end of one and the
start of the next. Without cuts, the gaps are used unchanged.

Each interval's text hint (ForeSeek's 3–5 word `scene_hint`) gets the profile's description of it, so the planner
reads it when it labels intervals: `"busy, speech, 2 cuts"` or `"static, silent"`.

### 5.3 Features for System-1

`next_interval` is the riskiest System-1 decision (research.md, System-1). The profile gives it numbers it can rank
on, at no extra cost:

```python
class IntervalActivity(BaseModel):
    mean_activity: float      # mean of a(t) over the span
    peak_activity: float
    speech_fraction: float    # share of bins with speech
    cuts: int
    loudest_onset: float | None   # seconds, the largest audio onset in the span
```

A prompted or single-pass scorer sees these as a short line per option; a trained one sees them as features.

### 5.4 Placing frames inside an interval

When `seek_interval` samples n frames from an interval, the frames go at activity-weighted quantiles mixed with
uniform positions (same `prior_mix`): busy moments inside the interval get more frames, quiet ones still get some.

### 5.5 Streaming: waking up

In streaming mode ActiveForager re-checks after a fixed `check_after_sec`. With the prior, the agent also wakes
early when the live signals jump: a bitrate, visual-change or audio-onset value above 3 MAD of the last 30 s. This
answers "tell me when something happens" questions sooner and skips checks while nothing changes. The same jumps
can start a new archive segment, alongside ActiveForager's histogram rule.

### 5.6 Matching the prior to the question

Busy is not the same as relevant, and which signal matters depends on the question:

| Question looks like | Profile | Weights |
| --- | --- | --- |
| an event or action ("when does the dog jump?") | `motion` | bitrate, visual change |
| speech ("what does she say about the price?") | `speech` | speech, audio energy |
| a scene or topic change ("what happens after the meeting?") | `cuts` | cuts, chapters |
| a static detail ("what is written on the sign?") | `off` | none: the skim is all uniform |

Choosing the profile is a System-1 decision point (`prior_profile`, options `motion | speech | cuts | off | none of
the above`), made once per question before the skim. Low confidence falls back to the default weights.

## 6. Where it lives in the code

```
uberlens/
  media/
    probe.py        # S1, S2, S6 from the container; S3, S4 from audio; S5 from thumbnails
    activity.py     # ActivityProfile, normalisation, cuts, reliability checks
  prior.py          # skim_times(), seed_intervals(), sample_in_interval(), wake_trigger()
```

Decoding goes through PyAV (BSD licensed; its wheels bundle an LGPL build of FFmpeg) or the `ffprobe` / `ffmpeg`
command line as a subprocess. Both are compatible with UberLens's MPL-2.0. Don't link a GPL build of FFmpeg into a
package we distribute.

## 7. Cost targets

- Container signals (S1, S2, S6) on a one-hour file: a few seconds, reading packet headers only.
- With audio (S3, S4) and thumbnails (S5): well under the cost of one vision-model call on the same video.
- The profile is computed once per file and cached.

M1 measures these on real files and records them here.

### First measurement (synthetic, 2026-11-22)

A 60 s test video: a static grey frame (0–20 s), a moving test pattern (20–30 s), static colour bars (30–45 s) and a
moving cellular pattern (45–60 s), with a tone that is loud only at 20–30 s. It was encoded three ways with
x264 at 25 fps, and the video packets read with `ffprobe` (S1, S2):

| Encode | Probe time | Bitrate CV | Keyframe-gap CV | kB/s per stretch (grey / test / bars / cellular) | Keyframes (s) |
| --- | --- | --- | --- | --- | --- |
| Variable bitrate (CRF 23, default GOP) | 0.07 s | 1.65 | 0.20 | 0 / 86 / 0 / 45 | 0, 10, **20, 30**, 40, **45**, 55 |
| Constant bitrate (800 kb/s) | 0.08 s | 0.04 | 0.20 | 99 / 100 / 99 / 100 | same |
| Fixed 2 s GOP, no scene cuts | 0.07 s | 1.50 | 0.00 | 0 / 81 / 0 / 110 | every 2 s |

What it shows:

- **Bitrate separates motion from stillness sharply** in variable-bitrate and fixed-GOP encodes, and the
  constant-bitrate encode is flat (CV 0.04), so the 0.15 reliability rule switches S1 off where it should.
- **Keyframes mark cuts** in the default encode: the cuts at 20, 30 and 45 s all got keyframes. The others (10, 40,
  55 s) are x264's 10 s timer. So "off-grid keyframe = cut" needs the timer grid estimated, not just the gap spread:
  a CV of 0.20 alone would not switch S2 off here, which is right, but the timer keyframes must still be dropped.
- **Fixed-GOP encodes hide cuts entirely** (keyframe-gap CV 0.00): S2 switches off and S5 has to find them.
- **Static stretches are invisible** to bitrate (0 kB/s for the grey frame and the colour bars), the failure mode
  that keeps half the skim uniform.
- **Cost:** reading the packets of a 60 s file took 0.07 s, roughly 4 s per hour of video if it scales linearly
  (to confirm on real long files in M1).

Change from this test: section 3's S2 rule becomes "estimate the keyframe timer (the most common gap) and treat
keyframes off that grid as cuts; switch S2 off when every keyframe is on the grid".

## 8. Failure modes

| Failure | What happens | Mitigation |
| --- | --- | --- |
| The answer is in a static, quiet stretch | Activity frames miss it | Half the skim stays uniform; `prior_profile = off` for static-detail questions |
| Constant-bitrate or fixed-GOP encode | S1 or S2 carry nothing | Reliability checks switch them off; S5 takes over cuts |
| Heavy re-encode (benchmark videos are YouTube downloads) | Signals smoothed | Per-video normalisation; this is the hard case the evaluation runs on |
| Grain, noise, constant camera motion | Bitrate high everywhere | Normalisation flattens it; reliability check may switch S1 off |
| Music or narration over everything | Audio signals flat or misleading | Flat rule switches them off; speech profile only when the question is about speech |
| One busy scene dominates | Activity frames cluster | Minimum spacing T / (2N) |

## 9. How we know it works

Run every comparison at the **same frame budget** as ForeSeek's uniform skim, on the same model.

**Variants**

1. `prior_mix = 0`: uniform skim, ForeSeek's Eq. 1 (the baseline).
2. `prior_mix = 1`: activity frames only.
3. `prior_mix = 0.5`, fixed default weights.
4. `prior_mix = 0.5` with `prior_profile` chosen per question.
5. Variant 4 with cut-snapped intervals (5.2) on and off.

**Measures**

- Accuracy and frames per question on LVBench and Video-MME (long), the long-video sets where a blind skim hurts
  most.
- **Evidence hit at skim**: the share of questions where at least one skim frame falls inside the ground-truth
  evidence span. It isolates the prior from the rest of the agent. It needs timestamped answers: LongVALE-style
  grounding sets and our in-house set.
- Rounds to answer: a better first look should need fewer rounds.
- Results split by question type (event, speech, static detail), to check that the prior helps where it should and
  does no harm where it shouldn't.
- Probe time per video hour.

**Rule:** the prior stays only if variant 3 or 4 matches or beats variant 1 on accuracy with no more frames, and
does no worse than 1 point on static-detail questions. If not, `prior_mix` defaults to 0 and the code is removed
at the next cleanup.

**Also check on original footage.** Benchmark videos are re-encoded, which weakens the signals; footage straight
from a camera or from UberScene should show a larger effect. The in-house set should include both.

## 10. UberScene footage

Video rendered by UberScene doesn't need guessing: its TSX file is the edit, so it knows every cut, caption and
audio cue exactly. When UberLens works on UberScene output, the scene's timeline can be passed in as the cut list
and chapters (S6), replacing S2 and S5. `@uberscene/codecs` can also read packet sizes directly from footage
without a separate FFmpeg call.

## 11. Milestones

These follow [design.md](design.md) section 10.

- **M1, explore** (no model needed): S1, S2, S3 and S6; normalisation, cuts and reliability checks; the partition
  for first intervals (design.md 5.1) and frame placement for `overview`. Tests on synthetic videos with known
  events (a static stretch, a busy stretch, a cut, a sound), each encoded three ways: variable bitrate, constant
  bitrate, fixed GOP. The tests check that peaks and cuts land where the events are, and that the reliability
  checks switch off the right signals.
- **M3 and M4, benchmark**: the comparison in section 9 against the uniform first look, on the benchmark's Find
  and Answer tasks. S4 (voice activity) and S5 (thumbnail change) if the first three signals leave a gap.
- **Later** (design.md section 11): matching the prior to the question as a logged decision (5.6), interval
  features for a fast scorer (5.3), streaming wake triggers (5.5), S7 motion vectors.
