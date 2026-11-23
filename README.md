# UberLens

An agent harness for video that picks the right time.

Agents can already execute an edit. Where they fail is picking: looking in the wrong place, choosing a weaker take,
cutting a beat early or late. UberLens is built for that one job. Given footage and what is needed, it finds the
moment, chooses the best candidate and sets exactly where it starts and ends.

It works by zooming. The agent asks to see a span of time, and the harness decides how to show it:

- **Map**: the whole source in one strip.
- **Section**: minutes, one frame per shot.
- **Passage**: 10 to 60 seconds, with the words.
- **Moment**: 1 to 8 seconds, a dense run of frames with the real sound.
- **Frame**: one instant at full resolution, or a crop.

At each step the agent narrows, compares candidates, and marks a range. The result is a list of selections with
in and out points and reasons, exported as JSON, a cut list, FFmpeg commands or an
[UberScene](https://github.com/prefix-tree/uberscene) file. UberLens does not edit; it hands its selections to
whatever does.

> [!WARNING]
> **Design stage.** There is no code yet. [docs/design.md](docs/design.md) is the design. Earlier research is
> frozen in [docs/archive](docs/archive).

## License

[Mozilla Public License 2.0](LICENSE).
