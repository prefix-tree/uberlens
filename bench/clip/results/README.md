# Building a clip: trial

A trial, not a measurement: one request, one run per model, and nobody judged whether the clips are good.
It shows that the loop from a request to a checked file works with real models.

## First trial (2026-11-24)

Request, on the 19-minute interview: "Make a clip of about 15 seconds of her answer about how many nights they
slept in the cave." The code surface, with the skill. File `2026-11-24T113237.json`. About $0.03.

| | Claude Haiku 5.5 | GPT 5.6 Luna |
| --- | --- | --- |
| A clip was produced | Yes | Yes |
| Length (15 s asked for) | 15.3 s | 14.5 s |
| Source span | 64.2 to 79.5 s | 60.5 to 75.0 s |
| Holds the answer (labelled at 64.3 to 69.9 s) | Yes | Yes |
| Passed `verify` | Yes | Yes |
| Edges marked without a look | 0 | 0 |
| Looked at its own clip | Yes | Yes |
| Requests | 8 | 11 |
| Input tokens | 132,906 | 169,666 |

- Both went from the request to a file that is what they asked for, and both looked at it before finishing.
- Both looked at the in and out points before marking, as the skill asks.
- **It is expensive in tokens**: four to six times a locate task. Building a clip takes many more steps.
- What this does not show: whether the cut points are good, whether the clip starts and ends cleanly to the
  ear, or whether another fifteen seconds would have been better. That needs a person, or the experiments on
  choosing and trimming.
