# Operations

Every function of the library, generated from the code. Times are seconds; a span is `[start, end]`.
A `video` is a file's name. A call that cannot be served raises `ValueError` and says what to change.

## `info`

```python
info(video: str) -> dict
```

Facts about a video: its length in seconds, its size, and what has been prepared for it.

Args:
    video: Name or path of the video.

Example:

```python
info("interview.mp4")
```

## `find`

```python
find(video: str, query: str = '', after: float | None = None, before: float | None = None, limit: int = 8, like: list[float] | None = None) -> list[dict]
```

Find candidate spans where the words of `query` are said. Best first.

It searches the transcript and matches words, not meaning: rephrase with words the speaker
would use. A candidate is a place to look, not an answer, and an empty list does not mean the
moment is absent: look at the map, or ask `coverage` what has not been looked at.

Args:
    video: Name or path of the video.
    query: Words to look for.
    after: Only candidates that start at or after this time, in seconds.
    before: Only candidates that end at or before this time, in seconds.
    limit: The most candidates to return.
    like: Not available yet: a span to find lookalikes of.

Returns:
    A list of {"start", "end", "text", "score", "how"}. "how" is "words"; "score" is an estimate.

Example:

```python
find("interview.mp4", "company almost failed", after=60, limit=5)
```

## `words`

```python
words(video: str, start: float, end: float) -> list[dict]
```

The words said in a span, each with its start and end time. From the transcript: an estimate.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span, in seconds.

Example:

```python
words("interview.mp4", 1, 4)
```

## `gaps`

```python
gaps(video: str, start: float, end: float, shortest: float = 0.15) -> list[list[float]]
```

The gaps between words in a span, as [start, end] pairs: where nobody is speaking, by the transcript.

Unlike `pauses`, this works when music or noise runs under the speech, because it does not need
silence. It is an estimate: an edge can be a few tenths of a second off.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span, in seconds.
    shortest: The shortest gap to report, in seconds.

Example:

```python
gaps("interview.mp4", 0, 5)
```

## `repeats`

```python
repeats(video: str, start: float, end: float) -> list[dict]
```

Words or phrases said twice in a row in a span: a stumble, a restart, a repeated take.

From the transcript, so it finds only what the transcript wrote down; a speech model often leaves
out a stutter. Each result gives the span of both sayings, so cutting `first` leaves one.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span, in seconds.

Returns:
    A list of {"text", "first": [start, end], "second": [start, end]}, in time order.

Example:

```python
repeats("interview.mp4", 0, 5)
```

## `pauses`

```python
pauses(video: str, start: float | None = None, end: float | None = None) -> list[list[float]]
```

Measured silent stretches in a span, as [start, end] pairs. A quarter of a second or longer.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Example:

```python
pauses("interview.mp4", 0, 5)
```

## `loudness`

```python
loudness(video: str, start: float, end: float) -> list[list[float]]
```

Measured loudness in a span, as [time, LUFS] pairs every tenth of a second. Louder is nearer zero.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span, in seconds. At most 120 seconds after `start`.

Example:

```python
loudness("interview.mp4", 0, 2)
```

## `onsets`

```python
onsets(video: str, start: float | None = None, end: float | None = None, rise: float = 10) -> list[float]
```

Instants where the sound gets suddenly louder: a hit, a beat, a word after a silence. Measured.

Use it to see whether cuts follow the music, or to put a cut on a beat.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.
    rise: How many decibels louder than the moment before. Lower finds more.

Example:

```python
onsets("interview.mp4", 0, 5)
```

## `cuts`

```python
cuts(video: str, start: float | None = None, end: float | None = None) -> list[float]
```

Times where the picture cuts to a new shot, measured. The first use on a video scans all of it.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Example:

```python
cuts("interview.mp4")
```

## `shots`

```python
shots(video: str, start: float | None = None, end: float | None = None) -> list[list[float]]
```

The shots in a span, as [start, end] pairs: the stretches between cuts.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Example:

```python
shots("interview.mp4", 0, 5)
```

## `change`

```python
change(video: str, start: float, end: float) -> list[list[float]]
```

How much each frame in a span differs from the frame before it, as [time, whole, part] triples.

`whole` is the mean difference over the frame (0 to 255): near zero means the frame repeats the one
before. `part` is the largest difference in any one of 24 parts of the frame, so a change in a
corner shows there. The first use on a video decodes all of it once.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span, in seconds.

Example:

```python
change("interview.mp4", 1, 1.2)
```

## `events`

```python
events(video: str, start: float | None = None, end: float | None = None) -> list[dict]
```

Where the picture changes abruptly, in the whole frame or in part of it: something appears, cuts, fades in or flashes. Measured.

Finds what `cuts` cannot: a picture appearing in one part of the frame, a title popping on, a fade, a
flash of a frame or two. Each part of the frame is compared with what is usual for that part nearby,
so steady motion elsewhere (a moving object, a ticker) does not hide a change. The frame is divided
into 16 columns and 9 rows for this.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Returns:
    A list of {"time", "frame", "frames", "kind", "amount", "area", "where", "centre"}, in time order.
    `time` and `frame` are the first frame that differs: for a fade, the first frame where any of it
    shows. `frames` is how many frames the change takes. `kind` is "part", "whole" (a cut), "fade" (it
    builds over several frames) or "flash" (it appears and goes within a few frames). `area` is the
    share of the frame that changed; `where` is its [left, top, right, bottom] as fractions of the
    frame, usable as a region; `centre` is [x, y] of the change, weighted by how much each part changed.

Example:

```python
events("interview.mp4")
```

## `freezes`

```python
freezes(video: str, start: float | None = None, end: float | None = None, shortest: int = 3) -> list[dict]
```

Stretches where the picture stops: each frame repeats the one before it. Measured.

For a stuck or duplicated stretch, or a still. To remove the repeats and keep one frame, cut from
`start` to `end`: the frame before `start` is the one that was held.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.
    shortest: The fewest repeated frames in a row that count. Footage at a lower frame rate than its
        file repeats single frames all the time; three in a row is a stop.

Returns:
    A list of {"start", "end", "first_frame", "frames"}: the time of the first repeated frame, the
    time of the first frame that moves again, the first repeated frame's number counted from 0, and
    how many frames repeat.

Example:

```python
freezes("interview.mp4")
```

## `observe`

```python
observe(video: str, start: float, end: float | None = None, focus: str = 'visual', purpose: str = '', region: list[float] | None = None) -> dict
```

Look at a span. The picture is shown to you after the program ends; a program cannot see it.

You choose the span and the focus; how many frames and how large is chosen for you.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span. Leave out to see the single frame showing at `start`.
    focus: visual (what is in the picture), motion (dense frames), speech or delivery (sound and
        pauses, a few frames), boundary (frames and sound right around one instant), change (the
        frames where the picture changes most, each with the frame before it).
    purpose: The question this look should answer, in a few words. Kept in the log.
    region: The part of the frame to show, as [left, top, right, bottom] in fractions of its width
        and height: [0, 0.5, 1, 1] is the lower half. The part is shown larger. Leave out for all of it.

Returns:
    {"id", "text"}: the observation's id and the statement of what it shows.

Example:

```python
observe("interview.mp4", 1, 4, "delivery", "where does the line start?")
```

## `sheet`

```python
sheet(video: str, times: list[float], labels: list[str] | None = None, purpose: str = '', region: list[float] | None = None) -> dict
```

Show frames from anywhere in a video as one picture, like a plot: one frame per time you give.

Use it to scan or compare many places at the cost of one look: one frame per shot, one per
candidate. The frames are small and are separate instants, so look closer at the one that matters
with `observe`. The picture is shown to you after the program ends; a program cannot see it.

Args:
    video: Name or path of the video.
    times: The instants to show, in seconds, in the order to draw them. At most 48. For a dense run
        at a steady rate, `every(start, end, step)` makes the list.
    labels: A short label to print under each frame, one per time (a rank, a length, a few words).
    purpose: The question this sheet should answer, in a few words. Kept in the log.
    region: The part of the frame to show, as [left, top, right, bottom] in fractions of its width
        and height. Leave out for all of it.

Returns:
    {"id", "text"}: the observation's id and the statement of what it shows.

Example:

```python
sheet("interview.mp4", [1, 2.5, 4], labels=["first", "second", "third"], purpose="which one is sharpest?")
```

## `overview`

```python
overview(videos: list[str], per: int = 3, purpose: str = '') -> dict
```

Show several videos on one picture: a few frames of each, in a row, with the video's name under each.

For comparing clips, putting them in order, or matching them to descriptions, at the cost of one
look where one look per clip would not fit in your context. Frames are spread from each video's
first frame to its last. Every frame is drawn in the shape of the first video.

Args:
    videos: Names or paths of the videos, in the order to draw them.
    per: How many frames of each video: 1 is its middle, 2 its first and last, 3 adds the middle.
        Videos times frames is at most 48.
    purpose: The question this picture should answer, in a few words. Kept in the log.

Returns:
    {"id", "text"}: the observation's id and the statement of what it shows.

Example:

```python
overview(["interview.mp4"], per=3, purpose="what is in each clip?")
```

## `seam`

```python
seam(first: str, second: str, frames: int = 3, purpose: str = '') -> dict
```

Show how one video would run into another: the last frames of the first beside the first frames of the second.

For judging whether two clips follow each other, or how a cut between them would look, before
joining anything.

Args:
    first: Name or path of the video that comes first.
    second: Name or path of the video that follows it.
    frames: How many consecutive frames of each to show, from 1 to 6.
    purpose: The question this picture should answer, in a few words. Kept in the log.

Returns:
    {"id", "text"}: the observation's id and the statement of what it shows.

Example:

```python
seam("interview.mp4", "interview.mp4", purpose="would these two join cleanly?")
```

## `observations`

```python
observations(video: str | None = None, focus: str | None = None, start: float | None = None, end: float | None = None) -> list[dict]
```

Looks already made, oldest first: what was asked, what was shown, and why.

Args:
    video: Only looks at this video.
    focus: Only looks with this focus.
    start: Only looks that reach past this time, in seconds.
    end: Only looks that begin before this time, in seconds.

Example:

```python
observations("interview.mp4", focus="delivery")
```

## `coverage`

```python
coverage(video: str, start: float | None = None, end: float | None = None) -> dict
```

What has been looked at in a span, how closely, and what has not been looked at at all.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Returns:
    {"looked": [{"start", "end", "gap", "id"}], "sheets": [{"id", "times"}], "never": [[start, end]]}.
    "gap" is the most seconds between two frames shown in that look: a small gap is a close look.
    A sheet shows separate instants, so it is listed apart and covers nothing in between.

Example:

```python
coverage("interview.mp4", 0, 5)
```

## `expand`

```python
expand(span: Span, before: float = 0, after: float = 0) -> Span
```

Widen a span by `before` seconds at its start and `after` at its end. Never starts before zero.

Example:

```python
expand([10, 14], before=2, after=3)
```

## `merge`

```python
merge(spans: list[Span], gap: float = 0) -> list[Span]
```

Join spans that overlap or lie within `gap` seconds of each other. Returns them in time order.

Example:

```python
merge([[1, 2], [1.5, 3], [5, 6]], gap=0.5)
```

## `minus`

```python
minus(span: Span, spans: list[Span]) -> list[Span]
```

The parts of `span` that none of `spans` covers.

Example:

```python
minus([0, 10], [[2, 3], [5, 12]])
```

## `every`

```python
every(start: float, end: float, step: float) -> list[float]
```

Times from `start` to `end`, `step` seconds apart: the list a sheet wants for a dense run at a steady rate.

Example:

```python
every(0, 2, 0.25)
```

## `mark`

```python
mark(video: str, start: float, end: float, reason: str = '', replaces: str | None = None) -> dict
```

Save a span as a selection to use in a clip. It snaps to whole frames.

The selection records which of your looks it rests on. If you never looked at its first or last
frame, it is still saved and says so: look at the edge with focus "boundary", then mark again.

Args:
    video: Name or path of the video.
    start: Where the selection starts, in seconds.
    end: Where it ends, in seconds. The frame showing at this time is the first one left out.
    reason: Why this span, in a few words. Kept with the selection.
    replaces: The id of an earlier selection this one corrects.

Returns:
    {"id", "video", "start", "end", "frames", "edges_not_seen", "rests_on"}.

Example:

```python
mark("interview.mp4", 1, 4, reason="the whole line, with a breath before it")
```

## `selections`

```python
selections() -> list[dict]
```

The selections saved so far, oldest first, leaving out any that a later one replaced.

Example:

```python
selections()
```

## `clip`

```python
clip(selections: list[str], name: str) -> dict
```

Cut selections, in the order given, into one video file with hard cuts. Frame-exact.

The clip is then a video like any other: look at it with `observe`, by the name returned.

Args:
    selections: Ids of selections, in the order they should play.
    name: A short name for the clip: letters, digits, "-" or "_".

Returns:
    {"clip", "duration", "segments"}: the clip's file name, its length, and for each selection where
    it came from in its source and where it sits in the clip.

Example:

```python
clip([s["id"] for s in selections()][:1], "example")
```

## `verify`

```python
verify(clip: str) -> dict
```

Check a clip by code: it decodes, has the right number of frames, and each part starts and ends on the frame chosen.

It also lists where the joins are, so you can look at them. Passing these checks does not mean the
clip is good: look at it.

Args:
    clip: The clip's name, as `clip` returned it.

Returns:
    {"ok", "problems", "warnings", "duration", "joins", "next"}. "joins" are times in the clip.

Example:

```python
verify("example")
```

## `note`

```python
note(observation: str, text: str) -> dict
```

Write down what you concluded from a look, in a sentence. Pictures leave your context; notes stay.

A picture can always be shown again. What you concluded from it cannot be recovered unless it is
written here. Notes appear in `status` and in `observations`.

Args:
    observation: The id of the look, like obs_000012.
    text: What you concluded, in a sentence: what is there, and what it means for the task.

Example:

```python
note(observe("interview.mp4", 1, 4)["id"], "the bar moves left to right; nothing else changes")
```

## `brief`

```python
brief(text: str) -> dict
```

Record the task exactly as it was given, so its requirements survive a shortened context.

Copy the request word for word: lengths, formats, file names, what must and must not be in the
result. Do not summarise it. It is shown at the top of `status`.

Args:
    text: The task, word for word.

Example:

```python
brief("Make a 15-second clip of the answer. Output: clip.mp4, 16:9.")
```

## `status`

```python
status() -> str
```

Where the task stands: the brief word for word, the selections, the clips, and what each look concluded.

Read it when you are unsure what you have already done, or after your context was shortened.

Example:

```python
status()
```

## `videos`

```python
videos() -> list[dict]
```

The videos you can use, and the clips made so far: length, size, and what is prepared for each.

Example:

```python
videos()
```
