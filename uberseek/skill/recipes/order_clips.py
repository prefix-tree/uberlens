# Put clips in order: see all of them on one picture, then check the joins of the order you propose.
# Run it once to see the clips; set `order` from what the picture shows; run it again to check the joins.
video = "1.mp4"  # the first clip
others = []  # the rest: ["2.mp4", "3.mp4", ...]
order = []  # your proposed order, once you have one: ["3.mp4", "1.mp4", "2.mp4"]

clips = [video] + others
overview(clips, per=3, purpose="what is in each clip, and which could follow which?")
pairs = [[order[i], order[i + 1]] for i in range(len(order) - 1)][:3]
for a, b in pairs:
    seam(a, b, purpose="does " + b + " follow " + a + "?")
{"clips": [[c, info(c)["duration"]] for c in clips], "joins_shown": pairs}
