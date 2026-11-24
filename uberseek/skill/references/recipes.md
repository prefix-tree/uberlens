# Recipes

Worked programs for common jobs. Each is a file in `recipes/` next to this folder and runs as written:
set the lines at the top, then run it (`execute`, or `uberseek run recipes/<name>.py --video <file>`).
They are starting points: change the measurements and the looks to fit the job.

## Build a clip of one line: find it, set its edges on pauses, look at both edges, mark, cut, check, look

`recipes/build_clip.py`

```python
# Build a clip of one line: find it, set its edges on pauses, look at both edges, mark, cut, check, look.
# Set the lines below. Returns the selection, the clip and the result of the checks.
video = "interview.mp4"
query = "slept in the cave"
name = "the-line"

hits = find(video, query, limit=5)
if hits:
    hit = hits[0]
    before = pauses(video, max(0, hit["start"] - 2), hit["start"] + 0.2)
    after = pauses(video, hit["end"] - 0.2, hit["end"] + 2)
    start = round((before[-1][0] + before[-1][1]) / 2, 3) if before else hit["start"]  # the middle of the pause before
    end = round((after[0][0] + after[0][1]) / 2, 3) if after else hit["end"]  # the middle of the pause after
    observe(video, start, None, "boundary", "does the clip start cleanly here?")
    observe(video, end, None, "boundary", "does the clip end cleanly here?")
    chosen = mark(video, start, end, reason="the line: " + hit["text"][:60])
    made = clip([chosen["id"]], name)
    checked = verify(name)
    observe(made["clip"], 0, made["duration"], "delivery", "does the whole clip play as intended?")
{"selection": chosen, "clip": made, "check": checked} if hits else {"found": 0}
```

## Before saying something is not in the video: look at what has not been looked at yet

`recipes/coverage_check.py`

```python
# Before saying something is not in the video: look at what has not been looked at yet.
# Looks at the longest unseen stretches first, and lists stretches seen only from far away.
video = "interview.mp4"
within = None  # or [start, end]

whole = within if within else [0, info(video)["duration"]]
covered = coverage(video, whole[0], whole[1])
unseen = sorted(covered["never"], key=lambda s: s[0] - s[1])[:4]
for span in unseen:
    observe(video, span[0], span[1], "visual", "not looked at before")
far = [{"span": [look["start"], look["end"]], "gap": look["gap"]} for look in covered["looked"] if look["gap"] > 5]
{"looks_before": len(covered["looked"]), "unseen_before": covered["never"], "looking_now": unseen, "seen_only_from_far": far}
```

## Choose an exact cut point near a rough time: propose places from measurements, then look at each

`recipes/cut_point.py`

```python
# Choose an exact cut point near a rough time: propose places from measurements, then look at each.
# Candidates are the middle of each pause and each measured cut; with neither, the ends of words.
video = "interview.mp4"
near = 512.0  # roughly where the cut should be, in seconds
reach = 2.0  # how far either side to consider

start, end = max(0, near - reach), near + reach
candidates = []
for pause in pauses(video, start, end):
    middle = round((pause[0] + pause[1]) / 2, 3)
    candidates.append({"at": middle, "why": "middle of a pause of " + str(round(pause[1] - pause[0], 2)) + " s"})
for cut in cuts(video, start, end):
    candidates.append({"at": cut, "why": "a measured cut"})
if not candidates and info(video)["has_sound"]:
    for word in words(video, start, end):
        candidates.append({"at": word["end"], "why": "end of the word '" + word["text"] + "'"})
candidates = sorted(candidates, key=lambda c: abs(c["at"] - near))[:3]
for c in candidates:
    observe(video, c["at"], None, "boundary", "does a cut land cleanly here?")
candidates
```

## Find something that is shown, where searching the words does not help

`recipes/find_picture.py`

```python
# Find something that is shown, where searching the words does not help.
# One frame from every shot goes on a sheet (two sheets when there are more than 24 shots).
# Read the sheets, then look closely at the shot that shows it with observe.
video = "reel.mp4"
looking_for = "two people with a telescope at dusk"
within = None  # or [start, end] to search inside one stretch

whole = within if within else [0, info(video)["duration"]]
found = shots(video, whole[0], whole[1])[:48]
for part in (found[:24], found[24:]):
    if part:
        middles = [round((s[0] + s[1]) / 2, 3) for s in part]
        sheet(video, middles, labels=[str(s[0]) + " to " + str(s[1]) for s in part], purpose="which shot shows: " + looking_for)
{"shots": len(found), "shown": found}
```

## Find where something is said, and confirm it by looking

`recipes/find_spoken.py`

```python
# Find where something is said, and confirm it by looking.
# Set the two lines below. Returns the candidates you were shown, best first.
video = "interview.mp4"
query = "company almost failed"

hits = find(video, query, limit=10)
shown = hits[:3]
for hit in shown:
    span = expand([hit["start"], hit["end"]], before=1.5, after=1.5)
    observe(video, span[0], span[1], "delivery", "is this where it is said: " + query)
{"found": len(hits), "shown": [{"start": h["start"], "end": h["end"], "text": h["text"], "score": h["score"]} for h in shown]}
```

## Gather candidates for a line from several phrasings, rank them by measurements, compare them on one sheet

`recipes/rank_candidates.py`

```python
# Gather candidates for a line from several phrasings, rank them by measurements, compare them on one sheet.
# A take in one shot, with a pause before and after it, is easier to cut out cleanly.
video = "interview.mp4"
queries = ["company almost failed", "we nearly went under", "ran out of money"]

hits = []
for query in queries:
    hits += find(video, query, limit=10)
ranked = []
for span in merge([[h["start"], h["end"]] for h in hits], gap=1):
    said = " ".join(w["text"] for w in words(video, span[0], span[1]))
    ranked.append(
        {
            "span": span,
            "seconds": round(span[1] - span[0], 2),
            "one_shot": len(shots(video, span[0], span[1])) == 1,
            "pause_before": len(pauses(video, max(0, span[0] - 1.5), span[0] + 0.2)) > 0,
            "pause_after": len(pauses(video, span[1] - 0.2, span[1] + 1.5)) > 0,
            "text": said[:160],
        }
    )
ranked = sorted(ranked, key=lambda c: -(int(c["one_shot"]) + int(c["pause_before"]) + int(c["pause_after"])))[:8]
if ranked:
    middles = [round((c["span"][0] + c["span"][1]) / 2, 3) for c in ranked]
    sheet(video, middles, labels=[c["text"][:40] for c in ranked], purpose="which take looks best?")
for c in ranked[:2]:
    observe(video, max(0, c["span"][0] - 1), c["span"][1] + 1, "delivery", "which take is cleanest?")
ranked[:5]
```
