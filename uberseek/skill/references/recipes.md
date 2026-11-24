# Recipes

Worked programs for common jobs. Each is a file in `recipes/` next to this folder and runs as written:
set the lines at the top, then run it (`execute`, or `uberseek run recipes/<name>.py --video <file>`).
They are starting points: change the measurements and the looks to fit the job.

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
# This looks at a stretch in up to four parts and returns the shots of each part.
# Read the pictures, then run it again with `within` set to the part that shows it, to go closer.
video = "reel.mp4"
looking_for = "two people with a telescope at dusk"
within = None  # or [start, end] to search inside one stretch

whole = within if within else [0, info(video)["duration"]]
length = whole[1] - whole[0]
parts = 1 if length <= 60 else min(4, int(length // 60) + 1)
out = []
for i in range(parts):
    start = round(whole[0] + i * length / parts, 3)
    end = round(whole[0] + (i + 1) * length / parts, 3)
    observe(video, start, end, "visual", "which picture shows: " + looking_for)
    out.append({"part": i + 1, "span": [start, end], "shots": shots(video, start, end)})
out
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

## Gather candidates for a line from several phrasings, rank them by measurements, look at the best

`recipes/rank_candidates.py`

```python
# Gather candidates for a line from several phrasings, rank them by measurements, look at the best.
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
ranked = sorted(ranked, key=lambda c: -(int(c["one_shot"]) + int(c["pause_before"]) + int(c["pause_after"])))
for c in ranked[:3]:
    observe(video, max(0, c["span"][0] - 1), c["span"][1] + 1, "delivery", "which take is cleanest?")
ranked[:5]
```
