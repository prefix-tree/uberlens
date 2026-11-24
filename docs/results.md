# Results

Everything measured so far, in one place, with what each result can and cannot support. The run files and
longer write-ups are in the repository under
[`bench/`](https://github.com/prefix-tree/uberseek/tree/main/bench).

::: warning Read this first
Almost everything here is a **trial**: few tasks, one to three runs per cell, small or single models. They show
whether something works and which way a change pushes. They do not rank models or prove a gain. The
experiments the design calls for, against baselines and with editors judging, have not been run.
:::

## The foundation: exact frames

Not a trial. These are tests that pass on every change.

- A frame fetched alone equals the same frame from playing the file straight through, on seven kinds of file:
  B-frames, variable frame rate, HEVC, VP9, timestamps that do not start at zero, a cut that hides frames,
  rotation.
- Any logged look can be made again from its log entry alone: the same frames, the same sound, the same
  picture byte for byte.
- A clip holds exactly the frames selected, and `verify` catches a cut one frame off.

## Can a model read the pictures?

Claude Sonnet 5.5 and GPT 5.6 Terra, 20 questions on generated clips with known answers, three repeats.

| Question | Claude | GPT |
| --- | --- | --- |
| The first picture that shows the square | 12/12 | 12/12 |
| The time printed on picture N | 12/12 | 12/12 |
| The pictures the scene changes between | 12/12 | 12/12 |
| The pictures whose tick is inside the silence | 12/12 | 12/12 |
| The picture at the marked instant | 12/12 | 12/12 |

- **Supports:** the picture format is readable by two strong models.
- **Does not support:** anything about hard real footage, or about weaker models.
- **What it caught:** asked for "frames", GPT first answered 0/12 in frame numbers of the video. The wording
  was fixed in the product.

[Post](./blog/can-a-model-read-the-pictures) · [files](https://github.com/prefix-tree/uberseek/tree/main/bench/reading/results)

## Code against plain tools

Claude Sonnet 5.5, six "find A, then the related B" tasks with computed answers, both surfaces, three repeats.

| | Code | Plain tools |
| --- | --- | --- |
| Right on the four sound tasks | 12/12 | 12/12 |
| Input tokens per run, mean | 29,499 | 41,827 |
| Requests per run | 4.7 | 4.8 |
| Counting a word in a long shot | 29,045 tokens | 89,402 tokens |
| A task needing two lookups | 29,001 tokens | 16,676 tokens |

- **Supports:** equal accuracy; code is cheaper when there is much data and dearer when there is little.
- **Does not support:** a general claim that code is better. One model, six tasks, and tasks that test
  searching and linking, not judging a picture.
- **What it caught:** two tasks had wrong computed answers because a measurement was wrong. Every program
  trusted the faulty list; the model reading the list on the tools surface corrected it.

[Post](./blog/code-against-plain-tools) · [files](https://github.com/prefix-tree/uberseek/tree/main/bench/compose/results)

## Building a clip

One request on a 19-minute interview, two small models, one run each.

| | Claude Haiku 5.5 | GPT 5.6 Luna |
| --- | --- | --- |
| Clip length (15 s asked for) | 15.3 s | 14.5 s |
| Holds the answer | Yes | Yes |
| Passed `verify` | Yes | Yes |
| Looked at both edges, and at the clip | Yes | Yes |

- **Supports:** the loop from a request to a checked file works with real models.
- **Does not support:** that the clips are good. Nobody judged them.

[Post](./blog/from-a-request-to-a-checked-clip) · [files](https://github.com/prefix-tree/uberseek/tree/main/bench/clip/results)

## Context management

The same clip request, one run per setting.

| Setting | Claude Haiku 5.5: input tokens | GPT 5.6 Luna: input tokens |
| --- | --- | --- |
| Pictures stay in the context for good | 217,515 | 137,063 |
| Pictures stay one step; notes stay | 163,089 | 90,488 |
| The same, with provider caching | 146,473 (101,103 from cache) | 134,491 (101,182 from cache) |

- **Supports:** taking pictures out after one step lowers input tokens with no loss on this task; caching
  turns about 70% of the rest into cache reads.
- **Does not support:** the exact percentages. Token counts vary by tens of thousands between runs.

[Post](./blog/pictures-that-stay-one-step) · [files](https://github.com/prefix-tree/uberseek/tree/main/bench/clip/results)

## The skill, with and without

Four draft locate tasks, two small models, both surfaces: 32 runs.

| Surface | Skill | Found the moment | Looked before answering |
| --- | --- | --- | --- |
| Code | On | 7 of 8 | 8 of 8 |
| Code | Off | 6 of 8 | 6 of 8 |
| Plain tools | On | 7 of 8 | 8 of 8 |
| Plain tools | Off | 6 of 8 | 6 of 8 |

- **Supports:** the skill changes behaviour: every run looked before answering.
- **Does not support:** a gain in accuracy. One more task per cell is within chance at this size.

[Files](https://github.com/prefix-tree/uberseek/tree/main/bench/locate/results)

## What these trials taught us about our own labels

- **Three of the five draft labels we tried were wrong.** A shot that began two seconds early, a question the
  video answers twice, a second shot that fits a description. The locate tasks were written by a model and
  need a person before they can score anything.
- **A computed answer is not ground truth either.** It is only as good as the measurement under it.

## Not yet measured

- Any comparison against a baseline: SAVE, full-video inference, or an agent with no harness.
- Whether comparing candidates against a brief gives better selections than ranking them, which is the
  project's central question.
- Anything on a public benchmark. The target is [AgenticVBench](./roadmap).
