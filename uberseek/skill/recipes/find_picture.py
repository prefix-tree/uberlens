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
