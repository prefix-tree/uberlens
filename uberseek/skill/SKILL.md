---
name: uberseek
description: Measure and look inside video files with UberSeek - see any span of a video as one labelled picture of numbered frames with the sound drawn under it, find where something is said, get exact times of words, pauses, cuts and shots, find flash frames, frozen frames and parts of the picture that change on their own, compare clips, check a cut point or a join, and cut chosen spans into a frame-exact file. Use this skill whenever a task involves a video file (.mp4, .mov, .mkv) and you need to know what is in it, where something happens, how clips differ or follow each other, where to cut, or whether an edit came out right - before writing FFmpeg or frame-extraction code by hand, even if the user only says "find the part where", "put these clips in order", "which clip matches", "cut out the bit where" or "check the result".
---

# UberSeek: a scripting environment for video

A video is far larger than what your next decision needs. UberSeek measures the picture and the sound exactly,
lets you narrow things down with code, and shows you only the places that need eyes, each as one labelled
picture. Use it for any job on video: finding a moment, comparing clips, choosing a cut point, removing or
keeping spans, checking an edit. It works like a shell for video:

| You want to | Use | Like |
| --- | --- | --- |
| Find where something is said | `find(video, query)` | `grep` |
| See a span of the footage | `observe(video, start, end, focus)` | `cat` |
| See many places at once, on one sheet | `sheet(video, times, labels)` | a plot |
| Turn chosen spans into a video file | `mark`, `clip`, `verify` | an editor's bin and a render |
| Keep track of the task | `brief`, `note`, `status`, `videos` | a notebook |
| Combine searches, measurements and looks | a program (`execute`, or `uberseek run`) | a shell script |

Measurements are the exact part: `words`, `pauses`, `loudness`, `cuts`, `shots`, and for change in the picture
`change`, `flashes`, `freezes`, `part_changes`. Memory is kept for you:
every look is logged, and `observations` and `coverage` read the log.

## What a program can do

A program is ordinary Python with the library's functions already defined. Its power comes from one fact:
**every function takes a video and times, and returns plain lists and dicts of times.** So the output of any
function can be the input of any other. A span is `[start, end]` in seconds; a search hit is a dict with
`start` and `end`.

There are four kinds of step. A program strings them together.

| Step | Functions | Gives |
| --- | --- | --- |
| **Propose** places to consider | `find` (what is said), `shots` and `cuts` (structure), `flashes`, `freezes` and `part_changes` (what cuts miss), `pauses` (silences), `coverage` (not yet seen) | Spans |
| **Measure** a span | `words`, `pauses`, `loudness`, `shots`, `cuts`, `change` (frame by frame) over that span | Values to compare |
| **Reshape** a set of spans | `expand`, `merge`, `minus`, and Python's own `sorted`, slicing, `if` | Fewer or better spans |
| **Look** | `observe` (one span, closely), `sheet` (many instants, one picture) | Pictures, after the program ends |

The usual order is propose, measure, reshape, look: code narrows many places to a few, and you look only at
those. Ways to combine them:

**Chain: one result bounds the next search.** Find A, then look for B only after it.

```python
first = find("interview.mp4", "cave", limit=1)
later = find("interview.mp4", "moon", after=first[0]["end"], limit=3) if first else []
[first, later]
```

**Fan out, measure, filter.** Measure every candidate and keep those that pass.

```python
hits = find("interview.mp4", "moon", limit=20)
alone = [h for h in hits if len(shots("interview.mp4", h["start"], h["end"])) == 1]
[[h["start"], h["end"]] for h in alone]
```

**Join two kinds of evidence.** A line that is said, lies in one shot, and has a pause before it.

```python
kept = []
for h in find("interview.mp4", "moon", limit=20):
    before = pauses("interview.mp4", max(0, h["start"] - 1.5), h["start"] + 0.2)
    if before and len(shots("interview.mp4", h["start"], h["end"])) == 1:
        kept.append({"span": [h["start"], h["end"]], "pause_before": round(before[-1][1] - before[-1][0], 2), "text": h["text"][:60]})
kept
```

**Rank, and keep the runner-up.** Sort by a measurement; return the first two, so a wrong measurement shows.

```python
ranked = sorted(shots("reel.mp4"), key=lambda s: s[0] - s[1])
{"longest": ranked[0], "runner_up": ranked[1:2], "of": len(ranked)}
```

**Subtract: what is left.** The parts of a span that something does not cover.

```python
whole = [0, info("interview.mp4")["duration"]]
speech_free = pauses("interview.mp4")
{"unseen": coverage("interview.mp4")["never"][:5], "talking": len(minus(whole, speech_free))}
```

**Sample for your eyes.** Turn spans into instants and put them on one sheet; then look closely at the one
that matters. A sheet costs one look however many frames it holds.

```python
found = shots("reel.mp4")[:24]
sheet("reel.mp4", [(s[0] + s[1]) / 2 for s in found], labels=[str(s[0]) + " to " + str(s[1]) for s in found],
      purpose="which shot shows the telescope?")
len(found)
```

**When cuts find nothing.** A flash frame, a held frame or a collage that builds strip by strip changes too
little of the picture, or too briefly, to be a cut. Ask for those, and put what they find on one sheet.

```python
found = {"flashes": flashes("reel.mp4"), "held": freezes("reel.mp4"), "parts": part_changes("reel.mp4")}
times = sorted([f[0] for f in found["flashes"]] + [p["start"] for p in found["parts"]])[:24]
if times:
    sheet("reel.mp4", times, purpose="what changes at each of these?")
{"flashes": found["flashes"][:6], "held": found["held"][:6], "parts": found["parts"][:6]}
```

**Go wide, then narrow, across programs.** A program cannot see, so it cannot decide from a picture. Let one
program propose and show; read the pictures; write the next program from what you saw.

```python
quiet = pauses("interview.mp4", 505, 512)          # after a sheet showed the line is here
for pause in quiet[:3]:
    observe("interview.mp4", (pause[0] + pause[1]) / 2, None, "boundary", "does a cut land cleanly here?")
quiet
```

What keeps a program useful:

- **Return little.** The last line is what comes back: a few spans, a count, a decision. The rest stays in
  the program and costs nothing.
- **Look last, at few things.** At most four looks per program. Narrow first.
- **Do not branch on a picture.** `observe` and `sheet` return an id and a text to the program, not what
  is in the frame.

## Building a clip

Finding a span is half the job. To turn choices into a video file: mark each span, cut them, check the
file, then look at it.

| Step | Function | What it does |
| --- | --- | --- |
| Save a choice | `mark(video, start, end, reason)` | Records the span, snapped to frames, with the looks it rests on. It tells you if you never looked at its first or last frame |
| Cut | `clip(selections, name)` | Joins selections in the order given, with hard cuts, frame-exact. Returns the clip's name and where each part sits in it |
| Check by code | `verify(name)` | The file decodes, has the right frames, and each part starts and ends on the frame chosen. Lists the joins |
| Look | `observe(name, ...)` | The clip is a video like any other |

```python
quiet = pauses("interview.mp4", 500, 520)
a = mark("interview.mp4", quiet[0][1], quiet[-1][0], reason="the answer, from the breath before it") if len(quiet) > 1 else None
made = clip([a["id"]], "cave-answer") if a else None
checked = verify("cave-answer") if made else None
if made:
    observe(made["clip"], 0, min(3, made["duration"]), "delivery", "does it start cleanly?")
{"selection": a, "clip": made, "check": checked}
```

- Mark only after you have looked at both edges with focus `boundary`. `mark` reports `edges_not_seen`
  when you have not; look, then mark again with `replaces`.
- `verify` passing means the file is what you asked for. It does not mean the clip is good. Look at every
  join it lists, and at the start and the end.
- You cannot hear a click or a clipped breath at a cut. Say the sound of the clip is "not heard".
- Hard cuts only: no transitions, captions, speed changes or music.

## Keeping track

Your context is not a safe place to keep things. Pictures are taken out of it after you have used them, and
a long task can have its context shortened, which loses details and often loses rules.

- **Record the task first:** `brief(text)`, word for word. Lengths, formats, file names, what must and must
  not be in the result. Do not summarise it.
- **After each look, write what you concluded:** `note(id, "the second take is cleaner; she looks at the
  camera")`. A picture can always be shown again by its id. What you concluded from it cannot be recovered
  unless it is in a note.
- **When unsure where you are, read `status()`:** the brief, the selections, the clips, and every note.
  Before you finish, read the brief there again and check the result against each requirement.
- `videos()` lists what you can use and what is prepared.

```python
brief("Make a clip of about 15 seconds of her answer about the cave. Output: one mp4, hard cuts only.")
seen = observe("interview.mp4", 500, 520, "delivery", "is this the answer?")
note(seen["id"], "the look covers 500 to 520 s; decide from the picture, then replace this note")
status()[:400]
```

## How to work

1. **Orient.** Record the task with `brief`. `videos()` and `info(video)` give lengths and what is prepared. A look at the whole video
   (`observe(video, 0, duration)`) gives a map: a frame per slice of time, what is said under each, and the
   sound and cuts along the bottom.
2. **Narrow with code, not with looks.** `find` for what is said. `shots` and `cuts` for structure.
   `pauses` for timing. Put several steps in one program and return only what you need next: a few
   candidates, a count, a decision. One program that finds, filters and looks costs one round trip; five
   single calls cost five.
3. **Look before you decide.** A search result or a measurement is a place to look, not an answer. Only a
   picture you were shown counts as something you saw. Then write a `note`: the picture will not stay.
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
- **A sheet is for scanning, not for judging.** Its frames are small and are separate instants. Use it to
  find which place matters, then `observe` that place.
- **Give spans you looked at.** If you report 1:36.8 to 1:39.0, a picture should show both edges.

## What a picture shows

One image per look. For `observe`: a title line (video, span, focus), then numbered frames in time order, left to right
and top to bottom. Under each frame, the words said from that frame until the next. At the bottom, the
sound strip: a tick for each numbered frame, silences shaded, cuts as red lines, and for focus `boundary` a
yellow line at the instant you asked about. You choose the span and the focus. How many frames and how
large is chosen for you, and the text with the picture says exactly what was shown. For `sheet`: the frames
you picked, in your order, each with its number, its time and your label, and no sound strip.

| Focus | Shows | Use it for |
| --- | --- | --- |
| `visual` | Frames, spread over the span | What is in the picture (the default) |
| `motion` | A dense run of frames | How something moves, over a few seconds |
| `delivery` | Some frames, the sound strip, the words | How a line is said and where the pauses are |
| `speech` | Few frames, the sound strip, the words | Where speech and silence are |
| `boundary` | Consecutive frames around one instant, two seconds of sound | Whether a cut lands cleanly there |

<!-- harness -->
## Using it here

You have `find`, `observe` and `sheet` as tools, and `execute` to run a program like the ones above. Use a
tool for a single step. Use a program when a task needs several steps or more data than fits in a reply.
In a program, call the functions directly, without `await`. A program cannot see: `observe` and `sheet`
inside it return the look's id and text, and the pictures (at most four per program) are shown to you with
the result.

For more, call `guide(topic)`:
<!-- /harness -->
<!-- shell -->
## Using it from a shell

Everything is one command, `uberseek`. Run it in the folder that holds the videos. State is kept
in `.uberseek/` in the current folder. Times are seconds, or `H:MM:SS.mmm`.

```sh
uberseek transcript interview.mp4                       # once per video; needed for find and for words
uberseek find interview.mp4 "company almost failed"     # candidates, as JSON
uberseek observe interview.mp4 41:12 41:38 --focus delivery --out look.png
uberseek run program.py --video interview.mp4           # a program; prints its result and picture paths
uberseek guide recipes                                  # print a reference file
```

Every operation above is also a command, with its arguments in order: `uberseek pauses interview.mp4 500 520`,
`uberseek sheet interview.mp4 '[5, 20, 61.5]'`, `uberseek videos`. `observe`, `sheet` and `run` print the path of each picture. Open that file to see it: the text alone is not the
look. A program is plain Python like the ones above: call the functions directly, without `await` or
imports, and end with the value to return.

For more, read these files next to this one (or `uberseek guide <topic>`):
<!-- /shell -->

| Topic | Read it when |
| --- | --- |
| `operations` | You need a function's exact arguments or what it returns |
| `looking` | You are choosing a span or a focus, or reading a picture closely |
| `programs` | A program failed, or you are unsure what Python is allowed |
| `recipes` | You want a worked program for a common job: a spoken moment, a picture, a cut point |
| `limits` | You wonder whether UberSeek can do something at all |
| `card` | You want the short version: one line per job, as shell commands |
