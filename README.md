# UberLens

An agent harness for video: one reusable harness that brings together what an agent needs to work with video.

It has two layers. The **base** is for exploring video: the agent says which span it wants to look at and what
for, and the harness decides how to show it, from a map of the whole source down to a moment with real sound or a
single frame. Everything shown is logged with exactly what was decoded. The base knows nothing about editing, so
question answering, search and review can be built on it too.

**Modules** sit on top. The first is selection: finding the moment that is needed, comparing candidates directly
with picture and sound, and choosing where the selection starts and ends among alternative cut points. The result
is a list of selections with reasons, exported as JSON, a cut list or an
[UberScene](https://github.com/prefix-tree/uberscene) file.

Later iterations add carrying out edits, reviewing the render and handling revisions to the same harness.

> [!WARNING]
> **Design stage.** There is no code yet. [docs/design.md](docs/design.md) is the design. Earlier research is
> frozen in [docs/archive](docs/archive).

## License

[Mozilla Public License 2.0](LICENSE).
