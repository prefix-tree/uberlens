# UberLens

A harness that lets an AI agent explore video and edit it, and a benchmark that measures how well it does both.

Agents fail at video by drowning: they transcribe or thumbnail everything, run out of budget and never finish the
edit. UberLens gives an agent you already use (Claude Code, Codex, any tool-calling model) a better way to work:

- **Explore.** Look only where it matters: a cheap first look guided by the file's own signals (bitrate, keyframes,
  audio), then targeted frames, crops and sound inside the stretches that look promising.
- **Remember.** Everything seen is stored outside the model's context, tied to the exact version of the file it came
  from, so a decision can always be traced to its evidence.
- **Edit.** Changes go through [UberScene](https://github.com/prefix-tree/uberscene)'s typed, undoable actions on one
  TSX file, never through hand-written FFmpeg commands.
- **Check.** Code checks first, then a critic that watches the rendered result and asks for one concrete fix per
  segment.

The benchmark runs the same model with and without the harness on footage that can be redistributed, and reports
cost next to accuracy.

> [!WARNING]
> **Design stage.** There is no code yet. [docs/design.md](docs/design.md) is the design; the research behind it is
> in [docs/](docs).

## License

[Mozilla Public License 2.0](LICENSE).
