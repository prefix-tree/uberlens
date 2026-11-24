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

## Pictures that stay one step, and a cached prefix (2026-11-24)

The same request, the same two cheap models, the code surface. Three settings, one run per model each.
Files `2026-11-24T125250.json` (the first two settings) and `2026-11-24T125534.json` (with caching). About $0.07 in all.

| Setting | Claude Haiku 5.5: input tokens | GPT 5.6 Luna: input tokens | Notes written (Haiku / Luna) | Clip correct |
| --- | --- | --- | --- | --- |
| Pictures stay in the context for good | 217,515 | 137,063 | 1 / 1 | Both |
| Pictures stay one step; notes stay | 163,089 | 90,488 | 3 / 5 | Both |
| The same, and the provider caches the fixed part | 146,473, of which 101,103 from cache | 134,491, of which 101,182 from cache | 3 / 5 | Both |

- **Taking pictures out after one step cut input tokens by 25% and 34%.** Every clip still held the answer,
  passed `verify`, and was looked at before the model finished.
- **The models wrote more notes** when told the picture would not stay: 3 and 5, against 1.
- **Caching made 69% and 75% of the input tokens cache reads.** By the account balance, a run cost about
  $0.016 at first, about $0.012 with pictures leaving, and about $0.007 with caching as well: roughly 60% less.
  The split between the first two is estimated from their token counts, since they were billed together.
- **What is left is the fixed part.** The skill and the tool definitions are about 6,700 tokens on every
  request, so ten requests carry 67,000 tokens of them. Caching makes them cheap; it does not make them fewer.

One run per cell. Token counts vary from run to run by tens of thousands (compare the two "pictures stay one
step" rows for Luna), so the direction is clear and the exact percentages are not.
