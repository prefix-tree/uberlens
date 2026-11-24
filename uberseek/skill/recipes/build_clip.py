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
