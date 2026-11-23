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
