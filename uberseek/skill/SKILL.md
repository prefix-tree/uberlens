---
name: uberseek
description: Explore video with UberSeek - find where something is said or shown, look at any span as one picture of numbered frames with the sound drawn under it, measure pauses, loudness and cuts, and choose exact in and out points. Use this skill whenever a task needs you to look inside a video file - locating a moment, checking what happens at a time, comparing takes, picking a clip or a cut point, answering a question about footage, or reviewing an edit - even if the user only says "find the part where", "what happens at 2:30", "pull the best quote" or names an .mp4, .mov or .mkv file.
---

# UberSeek: exploring video

A video is far larger than what your next decision needs. UberSeek lets you narrow it down with code and
look only where a judgment needs eyes. It works like a shell for video:

| You want to | Use | Like |
| --- | --- | --- |
| Find where something is said | `find(video, query)` | `grep` |
| See a span of the footage | `observe(video, start, end, focus)` | `cat` |
| Combine searches, measurements and looks | a program (`execute`, or `uberseek run`) | a shell script |

Measurements are the exact part: `words`, `pauses`, `loudness`, `cuts`, `shots`. Memory is kept for you:
every look is logged, and `observations` and `coverage` read the log.

## How to work

1. **Orient.** `info(video)` gives the length and what is prepared. A look at the whole video
   (`observe(video, 0, duration)`) gives a map: a frame per slice of time, what is said under each, and the
   sound and cuts along the bottom.
2. **Narrow with code, not with looks.** `find` for what is said. `shots` and `cuts` for structure.
   `pauses` for timing. Put several steps in one program and return only what you need next: a few
   candidates, a count, a decision. One program that finds, filters and looks costs one round trip; five
   single calls cost five.
3. **Look before you decide.** A search result or a measurement is a place to look, not an answer. Only a
   picture you were shown counts as something you saw.
4. **Zoom.** Start wide and go closer only where it matters: minutes, then a passage of 10 to 60 seconds,
   then a moment of a few seconds. For a cut point, look with focus `boundary` at one instant.
5. **Before saying something is not there, check `coverage`.** It says what you have not looked at.
6. **Answer with the span and what it rests on:** which picture or measurement decided it.

## Rules that keep you right

Each of these comes from a mistake actually made with this tool.

- **A number on a picture means that picture, not a frame of the video.** Every picture on a sheet has its
  number and its time printed in its corner. "Between 4 and 5" means the fourth and fifth picture. Read
  times from the printed labels.
- **Seen is not heard.** You get no sound. It is drawn as a strip: the wave, silences shaded. That shows
  where sound and pauses are. It cannot tell you tone, clarity or whether music drowns a voice. Say "not
  heard" for any judgment of that kind.
- **`find` matches words, not meaning.** Use words the speaker would say. Try two or three phrasings. An
  empty result does not mean the moment is absent: look at the map instead.
- **A measured cut can be wrong.** Flashes and dissolves are missed, so a "shot" may hold two. Look at a
  shot's first and last second before you report its edges.
- **The transcript is an estimate.** A word can be wrong or a little early or late. For an exact cut,
  trust the picture and the sound strip over a word's printed time.
- **A program trusts its data, so check what it picks.** `max()` over a list of pauses or shots cannot notice
  that two entries touch or that a shot holds a missed cut. Have the program return the runner-up as well as
  the winner, and look at the winner before you report it.
- **Give spans you looked at.** If you report 1:36.8 to 1:39.0, a picture should show both edges.

## What a picture shows

One image per look: a title line (video, span, focus), then numbered frames in time order, left to right
and top to bottom. Under each frame, the words said from that frame until the next. At the bottom, the
sound strip: a tick for each numbered frame, silences shaded, cuts as red lines, and for focus `boundary` a
yellow line at the instant you asked about. You choose the span and the focus. How many frames and how
large is chosen for you, and the text with the picture says exactly what was shown.

| Focus | Shows | Use it for |
| --- | --- | --- |
| `visual` | Frames, spread over the span | What is in the picture (the default) |
| `motion` | A dense run of frames | How something moves, over a few seconds |
| `delivery` | Some frames, the sound strip, the words | How a line is said and where the pauses are |
| `speech` | Few frames, the sound strip, the words | Where speech and silence are |
| `boundary` | Consecutive frames around one instant, two seconds of sound | Whether a cut lands cleanly there |

<!-- harness -->
## Using it here

You have `find` and `observe` as tools, and `execute` to run a program. Times are seconds. In a program
the functions are already defined: call them directly, without `await`, and end with the value to return.
A program cannot see: `observe` inside it returns the look's id and text, and the pictures (at most four
per program) are shown to you with the result.

```python
hits = find("interview.mp4", "company almost failed", limit=10)
best = hits[:3]
for hit in best:
    span = expand([hit["start"], hit["end"]], before=2, after=2)
    observe("interview.mp4", span[0], span[1], "delivery", "is this the admission?")
[{"start": h["start"], "end": h["end"], "text": h["text"]} for h in best]
```

For more, call `guide(topic)`:
<!-- /harness -->
<!-- shell -->
## Using it from a shell

Everything is one command, `uberseek` (run it with `uv run uberseek` inside the project). State is kept
in `.uberseek/` in the current folder. Times are seconds, or `H:MM:SS.mmm`.

```sh
uberseek transcript interview.mp4                       # once per video; needed for find and for words
uberseek find interview.mp4 "company almost failed"     # candidates, as JSON
uberseek observe interview.mp4 41:12 41:38 --focus delivery --out look.png
uberseek run program.py --video interview.mp4           # a program; prints its result and picture paths
uberseek guide recipes                                  # print a reference file
```

`observe` and `run` print the path of each picture. Open that file to see it: the text alone is not the
look. A program is plain Python in which the functions are already defined: call them directly, without
`await` or imports, and end with the value to return.

```python
hits = find("interview.mp4", "company almost failed", limit=10)
best = hits[:3]
for hit in best:
    span = expand([hit["start"], hit["end"]], before=2, after=2)
    observe("interview.mp4", span[0], span[1], "delivery", "is this the admission?")
[{"start": h["start"], "end": h["end"], "text": h["text"]} for h in best]
```

For more, read these files next to this one (or `uberseek guide <topic>`):
<!-- /shell -->

| Topic | Read it when |
| --- | --- |
| `operations` | You need a function's exact arguments or what it returns |
| `looking` | You are choosing a span or a focus, or reading a picture closely |
| `programs` | A program failed, or you are unsure what Python is allowed |
| `recipes` | You want a worked program for a common job: a spoken moment, a picture, a cut point |
| `limits` | You wonder whether UberSeek can do something at all |
