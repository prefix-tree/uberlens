# UberLens

An agent harness for video: one reusable harness that brings together what an agent needs to work with video.

It has two layers. The **base** is a programmable environment for exploring video. The agent writes small
programs against a typed video API to search, measure and filter footage, so the bulk of the data never enters
its context. Where a judgment needs eyes, it asks to be shown a span and says what for, and the harness decides
how to show it as images, from a map of the whole source down to a dense run of frames or a single frame. Sound
reaches the model as measurements and as drawn waveform strips; it does not hear yet.
Everything shown is logged with exactly what was decoded. The base knows nothing about editing, so question
answering, search and review can be built on it too. UberLens has no agent loop of its own: it runs inside an
existing agent harness such as Pydantic AI or Hermes.

**Modules** sit on top. The first is selection: finding the moment that is needed, comparing candidates directly
and choosing where the selection starts and ends among alternative cut points. The result
is a list of selections with reasons, exported as JSON, a cut list or an
[UberScene](https://github.com/prefix-tree/uberscene) file.

Later iterations add carrying out edits, reviewing the render and handling revisions to the same harness.

> [!WARNING]
> **Design stage.** There is no code yet. [docs/design.md](docs/design.md) is the design. Earlier research is
> frozen in [docs/archive](docs/archive).

## License

[Mozilla Public License 2.0](LICENSE).
