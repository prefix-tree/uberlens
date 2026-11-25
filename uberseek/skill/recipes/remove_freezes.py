# Remove stretches where the picture is stuck: measure them, keep everything else, cut, check, look at the joins.
# One held frame of each stretch stays; the repeats of it go.
video = "interview.mp4"
name = "unstuck"  # the clip to make

stuck = freezes(video)
whole = [0, info(video)["duration"]]
if stuck:
    kept = minus(whole, [[f["start"], f["end"]] for f in stuck])
    marked = [mark(video, a, b, reason="between two stuck stretches") for a, b in kept]
    made = clip([m["id"] for m in marked], name)
    checked = verify(name)
    for join in made["segments"][1:3]:
        observe(made["clip"], join["clip"][0], None, "boundary", "does the picture run on across this join?")
    result = {"removed": stuck, "clip": made["clip"], "duration": made["duration"], "problems": checked["problems"]}
else:
    observe(video, whole[0], whole[1], "change", "nothing is stuck by measurement: where does the picture change?")
    result = {"removed": [], "note": "no stretch of three or more repeated frames was found"}
result
