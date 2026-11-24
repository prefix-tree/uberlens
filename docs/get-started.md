# Get started

UberSeek is a Python package with a command line. It needs Python 3.11 or later,
[uv](https://docs.astral.sh/uv/) and FFmpeg.

```sh
git clone https://github.com/prefix-tree/uberseek
cd uberseek
uv sync --all-extras
```

Everything it remembers is kept in `.uberseek/` in the folder you run it from: the log of looks, the pictures,
the transcript and the measurements of each file.

## Look at a video

```sh
uv run uberseek observe interview.mp4 41:12 41:38 --focus delivery
uv run uberseek observe interview.mp4 41:20.5 --focus boundary
```

`observe` writes one picture and prints what it shows: which frames, how far apart, where the cuts and pauses
are. Times are seconds, or `H:MM:SS.mmm`.

| Focus | Shows |
| --- | --- |
| `visual` | Frames spread over the span (the default) |
| `motion` | A dense run of frames |
| `delivery` | Some frames, the sound strip, the words |
| `speech` | Few frames, the sound strip, the words |
| `boundary` | Consecutive frames around one instant, and two seconds of sound |

A wide span is shown coarsely and a short one densely. To see more detail, ask for less time.

## Search and transcribe

```sh
uv run uberseek transcript interview.mp4                    # once per video
uv run uberseek find interview.mp4 "slept in the cave"      # candidate spans, as JSON
```

`find` searches the transcript and matches words, not meaning.

## Run a program

A program is plain Python in which the operations are already defined. It runs in a sandbox, and only the
value of its last line comes back, with the pictures of anything it looked at.

```python
hits = find("interview.mp4", "slept in the cave", limit=10)
for hit in hits[:2]:
    span = expand([hit["start"], hit["end"]], before=1.5, after=1.5)
    observe("interview.mp4", span[0], span[1], "delivery", "is this the line?")
[{"start": h["start"], "end": h["end"], "text": h["text"]} for h in hits[:5]]
```

```sh
uv run uberseek run program.py --video interview.mp4
```

## Build a clip

```sh
uv run uberseek mark interview.mp4 64.2 79.5 --reason "her answer about the nights in the cave"
uv run uberseek clip cave-answer sel_000001
uv run uberseek verify cave-answer
```

The clip is written to `.uberseek/clips/`. `verify` checks that the file is what was asked for. It does not
say the clip is good.

## Keep track

```sh
uv run uberseek brief "Make a 15-second clip of her answer about the cave. One mp4, hard cuts only."
uv run uberseek note obs_000012 "the second take is cleaner"
uv run uberseek status
```

The brief, the selections, the clips and every note are kept in `.uberseek/WORKING.md`, rewritten after every
step.

## Use it from an agent

With [Pydantic AI](https://ai.pydantic.dev/) as the host:

```python
from pydantic_ai import Agent
from uberseek import Project
from uberseek.host.pydantic_ai import harness

agent = Agent("anthropic:claude-sonnet-5.5", capabilities=harness(Project("."), videos=["interview.mp4"]))
```

`harness` gives the agent the tools, the [skill](./skill), and the rule that a picture stays in its context
for one step only.

With a coding agent such as Claude Code, install the skill and let the agent use the command line:

```sh
uv run uberseek skill install
```

## Check that it works

```sh
uv run pytest
uv run uberseek reproduce      # makes every logged look again and compares
```
