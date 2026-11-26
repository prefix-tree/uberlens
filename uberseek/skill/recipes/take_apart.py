# Take an edit apart: when each element appears, where in the frame, and what flashes. Measure, then look once.
video = "reel.mp4"
start = 0.0  # the stretch to take apart, in seconds
end = 4.0
columns = 6  # how many columns `where` divides the frame into

found = events(video, start, end)
timeline = []
for e in found:
    column = min(columns - 1, int(e["centre"][0] * columns))
    timeline.append({"time": e["time"], "frame": e["frame"], "kind": e["kind"], "column": column, "where": e["where"]})
observe(video, start, end, "change", "what appears at each measured event?")
if found:
    biggest = sorted(found, key=lambda e: -e["amount"])[0]
    observe(video, biggest["time"], None, "visual", "the largest change, in its part of the frame", region=biggest["where"])
{"events": timeline, "cuts": cuts(video, start, end), "stuck": freezes(video, start, end)}
