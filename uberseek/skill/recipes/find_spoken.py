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
