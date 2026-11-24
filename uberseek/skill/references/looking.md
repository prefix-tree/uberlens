# Looking: spans, focus and reading a picture

You state how much time to look at and what the look is for. UberSeek decides how many frames to show and
how large, and tells you exactly what it showed. A wide span is shown coarsely; a short one, densely. So to
see more detail, ask for less time.

## How the span decides what you get

| Span | Level | Frames shown | Words | Sound strip |
| --- | --- | --- | --- | --- |
| One instant (no end) | Frame | 1 frame, as large as the picture allows | No | No |
| Up to 8 seconds | Moment | Up to 16 frames | Under each frame | The wave |
| Up to 60 seconds | Passage | Up to 24 frames, about one every 2 seconds | Under each frame | Only with focus `speech` or `delivery` |
| Up to 10 minutes | Section | One frame per shot when there are 8 shots or more, otherwise 24 equal slices | Under each frame, cut short | Measured loudness |
| Longer | Map | 32 equal slices of the span | Under each frame, cut short | Measured loudness |

The text that comes with a picture states the level, how many frames, how far apart they are, and how many
frames the span really holds. "16 frames, 0.4 s apart. The span holds 151 frames" means you saw one frame
in ten: something shorter than 0.4 seconds can hide between two pictures.

## Focus

| Focus | Frames | Sound | Use it when |
| --- | --- | --- | --- |
| `visual` | By the table above | By the table above | You want to know what is in the picture |
| `motion` | Up to 16, evenly through the span | Only for a moment | You are judging a movement: a gesture, a hand-over, an entrance. Keep the span to a few seconds |
| `delivery` | Up to 12 | Always | You are judging how a line is said: pauses, pace, where it starts and stops |
| `speech` | 4 | Always | You only need where speech and silence are |
| `boundary` | 8 consecutive frames, 4 before the instant and 4 from it | 2 seconds, centred on the instant | You are choosing an exact in or out point |

For `boundary`, give one time (no end). If you give a span, its middle is used.

## Reading a picture

- **Title line.** Video, span and focus. When a program returns several pictures, the title says which is
  which.
- **Numbered frames.** Each has its number and its time in the top-left corner, like `7  0:03.200`. Order
  is left to right, then top to bottom. Refer to a frame by its number or its printed time. The number is
  not a frame count of the video.
- **Words under a frame.** What was said from that frame until the next one shown. A long passage is cut
  with "…"; the text with the picture has it in full. Words come from the transcript and can be wrong.
- **Sound strip.** Time runs left to right across the same span as the frames (for `boundary`, across two
  seconds around the instant).
  - Small numbered ticks on top: where each numbered frame sits in time.
  - Blue shape: the sound. For spans up to 60 seconds it is the wave on a decibel scale, so quiet speech is
    still visible. For longer spans it is measured loudness.
  - Dark shaded stretches: measured silences, a quarter of a second or longer.
  - Red vertical lines: measured cuts.
  - Yellow vertical line: the instant you asked about (`boundary` only).
  - Words along the bottom (`speech`, `delivery`, `boundary`): each starts where it is said.
- **No strip** means the video has no sound, or the look did not call for it.

## A sheet: many places on one picture

`sheet(video, times, labels)` draws one frame for each time you give, in your order, up to 24. It is the
cheap way to scan or compare: one look, however many frames.

- Each frame has its number and its time in the corner, and your label under it.
- The frames are small (about 320 pixels wide when there are many), so read a sheet for "which one", not
  for fine detail.
- They are separate instants. Nothing between two frames was shown, there is no sound strip, and
  `coverage` lists a sheet apart from looks at spans.
- Good uses: one frame per shot, one per search hit, the middle of each stretch not yet looked at, the
  first and last frame of a candidate.
- Follow a sheet with `observe` on the place it pointed to.

## Choosing a cut point

1. Find the rough place with a `delivery` look over the line.
2. Get exact candidates from measurements: the end of a word (`words`), the start or end of a pause
   (`pauses`), a cut (`cuts`).
3. Look at each candidate with `boundary`. A clean cut usually sits in a shaded silence, after the last
   word's mark, with nothing changing sharply between the frames either side of the yellow line.
4. Say what you could not judge: whether a breath or a trailing sound is audible is "not heard".

## Looking again

`show_again(id)` (a tool) or opening the saved picture file shows a past look without decoding anything.
`observations(video)` lists past looks; `coverage(video, start, end)` says what has been looked at, how
closely (`gap` is the most seconds between two frames shown), and what has never been looked at.
