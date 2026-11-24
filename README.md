# UberSeek

An agent harness for video: one reusable harness that brings together what an agent needs to work with video.

It has two layers. The **base** is a programmable environment for exploring video. The agent writes small
programs against a typed video API to search, measure and filter footage, so the bulk of the data never enters
its context. Where a judgment needs eyes, it asks to be shown a span and says what for, and the harness decides
how to show it as images, from a map of the whole source down to a dense run of frames or a single frame. Sound
reaches the model as measurements and as drawn waveform strips; it does not hear yet.
Everything shown is logged with exactly what was decoded. The base knows nothing about editing, so question
answering, search and review can be built on it too. UberSeek has no agent loop of its own: it runs inside an
existing agent harness, Pydantic AI.

**Modules** sit on top. The first is selection: finding the moment that is needed, comparing candidates directly
and choosing where the selection starts and ends among alternative cut points. The result
is a list of selections with reasons, exported as JSON, a cut list or an
[UberScene](https://github.com/prefix-tree/uberscene) file.

Later iterations add carrying out edits, reviewing the render and handling revisions to the same harness.

> [!NOTE]
> **Early.** Built so far: exact frames and sound, the observation log, cuts, the transcript, a small library
> with `find` over the transcript, and a sandboxed executor. The selection module is not. [docs/design.md](docs/design.md)
> is the design. Earlier research is frozen in [docs/archive](docs/archive).

## Try it

Needs Python 3.11 or later, [uv](https://docs.astral.sh/uv/) and FFmpeg.

```sh
uv sync --all-extras
uv run uberseek observe interview.mp4 41:12 41:38 --focus delivery
uv run uberseek observe interview.mp4 41:20.5 --focus boundary
uv run uberseek reproduce          # make every logged observation again and compare
uv run uberseek transcript interview.mp4   # once; later looks show the words under the frames
uv run pytest
```

`observe` writes one picture and says what it shows: which frames, how far apart, where the cuts and the
pauses are, and what is said. The log and the pictures are kept in `.uberseek/` in the current folder.

From an agent, with Pydantic AI as the host:

```python
from pydantic_ai import Agent
from uberseek import Project
from uberseek.host.pydantic_ai import toolset

tools = toolset(Project("."), videos=["interview.mp4"])   # find, observe, execute
agent = Agent("anthropic:claude-sonnet-5.5", toolsets=[tools])
```

With `execute`, the model writes a short Python program against the library; it runs in a sandbox and only
its result comes back, with the pictures of anything it looked at:

```python
hits = find("interview.mp4", "company almost failed")
span = expand([hits[0]["start"], hits[0]["end"]], before=5, after=8)
observe("interview.mp4", span[0], span[1], "delivery")
{"candidates": len(hits), "best": hits[0]["text"]}
```

`sheet` draws frames picked from anywhere in the video on one picture, which costs one look:

```python
found = shots("reel.mp4")[:24]
sheet("reel.mp4", [(s[0] + s[1]) / 2 for s in found], labels=[str(s[0]) + " to " + str(s[1]) for s in found])
```

`toolset(..., surface="tools")` offers the same operations one call at a time instead. `find` searches the
transcript and matches words, not meaning.

## The skill

`uberseek/skill/` is an Agent Skill that teaches an agent how to use all of this: the operations, how to
work, how to read a picture, worked programs, and what UberSeek cannot do. Its references are generated from
the code and its examples are run by the tests.

```sh
uv run uberseek skill install            # copies it to .claude/skills/uberseek for Claude Code and similar agents
uv run uberseek guide                    # print the core
uv run uberseek guide recipes            # print one reference: operations, looking, programs, recipes, limits
uv run uberseek run program.py --video interview.mp4
```

In the Pydantic AI harness the skill is on by default: its core is the instructions, and a `guide` tool
returns the references on request.

## Measurements

```sh
uv run python -m bench.footage.fetch   # six open-licence videos into data/footage/, checked by hash
uv run python -m bench.reading.run     # can a model read the pictures? needs an OpenRouter key
uv run python -m bench.locate.run      # trial of the locate tasks on both tool surfaces
```

Results so far are in [bench/reading/results](bench/reading/results/README.md). The locate tasks in `bench/footage/locate.toml` are drafts until a person confirms each one.

## Docs site

The site is built with VitePress from `docs/`: the home page is `docs/index.md` and the design is
`docs/design.md`, the one maintained document.

```sh
pnpm install
pnpm docs:dev      # local preview
pnpm docs:build    # static site in docs/.vitepress/dist
```

Pushing to `main` deploys it to GitHub Pages (`.github/workflows/docs.yml`).

## License

[Mozilla Public License 2.0](LICENSE).
