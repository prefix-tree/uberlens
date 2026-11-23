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
> **Early.** The first milestone (M0) is built: exact frames and sound, the observation log, and `observe`
> as a tool. The typed API, the executor and the selection module are not. [docs/design.md](docs/design.md)
> is the design. Earlier research is frozen in [docs/archive](docs/archive).

## Try it

Needs Python 3.11 or later, [uv](https://docs.astral.sh/uv/) and FFmpeg.

```sh
uv sync --all-extras
uv run uberseek observe interview.mp4 41:12 41:38 --focus delivery
uv run uberseek observe interview.mp4 41:20.5 --focus boundary
uv run uberseek reproduce          # make every logged observation again and compare
uv run pytest
```

`observe` writes one picture and says what it shows: which frames, how far apart, and where the sound has
pauses. The log and the pictures are kept in `.uberseek/` in the current folder.

From an agent, with Pydantic AI as the host:

```python
from pydantic_ai import Agent
from uberseek import Project
from uberseek.host.pydantic_ai import toolset

agent = Agent("anthropic:claude-sonnet-5-5", toolsets=[toolset(Project("."))])
```

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
