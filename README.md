# UberLens

An agent harness for video: one reusable harness that brings together what an agent needs to work with video.

It is built in iterations. The first is about understanding video moments. Agents can already execute an edit;
where they fail is picking: looking in the wrong place, choosing a weaker take, cutting a beat early or late. So
the harness starts there: given footage and what is needed, it finds the moment, chooses the best candidate and
sets exactly where it starts and ends.

It works by zooming. The agent asks to see a span of time, and the harness decides how to show it:

- **Map**: the whole source in one strip.
- **Section**: minutes, one frame per shot.
- **Passage**: 10 to 60 seconds, with the words.
- **Moment**: 1 to 8 seconds, a dense run of frames with the real sound.
- **Frame**: one instant at full resolution, or a crop.

At each step the agent narrows, compares candidates, and marks a range. The result is a list of selections with
in and out points and reasons, exported as JSON, a cut list, FFmpeg commands or an
[UberScene](https://github.com/prefix-tree/uberscene) file.

Later iterations add carrying out edits, reviewing the render and handling revisions to the same harness.

> [!WARNING]
> **Design stage.** There is no code yet. [docs/design.md](docs/design.md) is the design. Earlier research is
> frozen in [docs/archive](docs/archive).

## License

[Mozilla Public License 2.0](LICENSE).
