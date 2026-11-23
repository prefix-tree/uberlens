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
