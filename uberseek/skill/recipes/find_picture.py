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
