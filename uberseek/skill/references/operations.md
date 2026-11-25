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

How much the picture changes at each frame of a span, measured: [time, whole, part] for every frame.

"whole" is the mean change from the frame before over the whole picture, "part" the change of the
eighth-by-eighth part that changed most, both in percent of the most a pixel can change. A cut is
high in both; a strip or a corner changing is high in "part" only; a held picture is near 0 in both.
The first use on a video scans all of it.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span, in seconds. At most 60 seconds after `start`.

Example:

```python
change("interview.mp4", 1, 2)
```

## `flashes`

```python
flashes(video: str, start: float | None = None, end: float | None = None) -> list[list[float]]
```

Flash frames, measured: one to three frames unlike the frames on both sides, as [start, end] pairs.

A flash to white or black, or a single frame of another shot. `cuts` misses most of them or reports
one as a cut. The first use on a video scans all of it.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Returns:
    [start, end] pairs: the first flash frame, and the frame after the last, where the picture returns.

Example:

```python
flashes("interview.mp4")
```

## `freezes`

```python
freezes(video: str, start: float | None = None, end: float | None = None, shortest: float = 0.2) -> list[list[float]]
```

Where the picture is held, measured: no part of it changes from one frame to the next.

A frozen frame, a still or a title. Set `shortest` to 0 to find even a single repeated frame. The
first use on a video scans all of it.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.
    shortest: The shortest hold to report, in seconds.

Returns:
    [start, end] pairs: the first held frame, and where the picture changes again.

Example:

```python
freezes("interview.mp4", shortest=0.5)
```

## `part_changes`

```python
part_changes(video: str, start: float | None = None, end: float | None = None) -> list[dict]
```

Where one part of the picture changes abruptly and then stays, while the rest holds. Measured.

A strip of a collage appearing, a picture in a picture switching, a caption box popping in. `cuts`
sees none of these, because most of the frame does not change. The first use on a video scans all of it.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds. Leave out for the beginning.
    end: End of the span, in seconds. Leave out for the end of the video.

Returns:
    A list of {"start", "end", "where", "change"}. "where" is [left, top, right, bottom] as shares of
    the width and height, to the nearest eighth. "change" is the most a part changed, in percent.

Example:

```python
part_changes("interview.mp4", 0, 5)
```

## `observe`

```python
observe(video: str, start: float, end: float | None = None, focus: str = 'visual', purpose: str = '') -> dict
```

Look at a span. The picture is shown to you after the program ends; a program cannot see it.

You choose the span and the focus; how many frames and how large is chosen for you.

Args:
    video: Name or path of the video.
    start: Start of the span, in seconds.
    end: End of the span. Leave out to see the single frame showing at `start`.
    focus: visual (what is in the picture), motion (dense frames), speech or delivery (sound and
        pauses, a few frames), boundary (frames and sound right around one instant).
    purpose: The question this look should answer, in a few words. Kept in the log.

Returns:
    {"id", "text"}: the observation's id and the statement of what it shows.

Example:

```python
observe("interview.mp4", 1, 4, "delivery", "where does the line start?")
```

## `sheet`

```python
sheet(video: str, times: list[float], labels: list[str] | None = None, purpose: str = '') -> dict
```

Show frames from anywhere in a video as one picture, like a plot: one frame per time you give.

Use it to scan or compare many places at the cost of one look: one frame per shot, one per
candidate. The frames are small and are separate instants, so look closer at the one that matters
with `observe`. The picture is shown to you after the program ends; a program cannot see it.

Args:
    video: Name or path of the video.
    times: The instants to show, in seconds, in the order to draw them. At most 24.
    labels: A short label to print under each frame, one per time (a rank, a length, a few words).
    purpose: The question this sheet should answer, in a few words. Kept in the log.

Returns:
    {"id", "text"}: the observation's id and the statement of what it shows.

Example:

```python
sheet("interview.mp4", [1, 2.5, 4], labels=["first", "second", "third"], purpose="which one is sharpest?")
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
