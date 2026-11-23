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
